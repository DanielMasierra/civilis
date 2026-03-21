"""
LexJal — Servidor MCP (Model Context Protocol)
Expone el agente jurídico como herramienta MCP para conectarlo con:
  - Claude.ai (claude.ai/settings/integrations)
  - ChatGPT (a través de OpenAPI spec)
  - Cualquier cliente compatible con MCP

Uso:
  python -m backend.mcp.server

Luego en Claude.ai: Settings → Integrations → Add custom integration
URL: https://tu-dominio.com/mcp
"""
import asyncio
import json
import sys
import os

# Asegura que el módulo puede importar el paquete backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from backend.config import get_settings
from backend.agent.agent import get_agent
from backend.middleware.rate_limiter import get_rate_limiter

settings = get_settings()

# Inicializar servidor MCP
server = Server("lexjal")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Define las herramientas disponibles en LexJal MCP."""
    return [
        types.Tool(
            name="consulta_juridica_civil",
            description=(
                "Orientación jurídica en materia civil de México. "
                "Especializado en el Código Civil de Jalisco y legislación federal. "
                "Responde preguntas sobre: herencias, divorcios, contratos, arrendamiento, "
                "propiedad, obligaciones civiles, registro civil, pensiones alimenticias y más. "
                "Cita artículos específicos de la ley. Una consulta gratuita por día."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pregunta": {
                        "type": "string",
                        "description": (
                            "La consulta jurídica civil en lenguaje natural. "
                            "Incluye el mayor contexto posible para una respuesta más precisa."
                        ),
                        "minLength": 10,
                        "maxLength": 2000,
                    },
                    "user_identifier": {
                        "type": "string",
                        "description": "Identificador opcional del usuario para el rate limit.",
                        "default": "mcp_anonymous",
                    },
                },
                "required": ["pregunta"],
            },
        ),
        types.Tool(
            name="estado_consultas",
            description="Verifica cuántas consultas gratuitas le quedan al usuario en el día.",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_identifier": {
                        "type": "string",
                        "description": "Identificador del usuario.",
                        "default": "mcp_anonymous",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Maneja la ejecución de las herramientas MCP."""

    if arguments is None:
        arguments = {}

    # ── Herramienta: consulta_juridica_civil ──────────────────────────────────
    if name == "consulta_juridica_civil":
        pregunta = arguments.get("pregunta", "")
        user_key = f"mcp:{arguments.get('user_identifier', 'anonymous')}"
        limiter = get_rate_limiter()

        # Verificar límite
        puede = await limiter.puede_consultar(user_key)
        if not puede:
            return [
                types.TextContent(
                    type="text",
                    text=(
                        "⚠️ Has agotado tu consulta gratuita del día.\n\n"
                        "Tu acceso se renovará mañana. Para consultas ilimitadas, "
                        "visita lexjal.com y conoce nuestros planes."
                    ),
                )
            ]

        # Llamar al agente
        agent = get_agent()
        try:
            resultado = await agent.consultar(pregunta=pregunta)
            await limiter.registrar_consulta(user_key)
            restantes = await limiter.consultas_restantes(user_key)

            # Formatear respuesta con fuentes
            respuesta = resultado["respuesta"]

            if resultado["fuentes"]:
                fuentes_txt = "\n\n---\n📚 **Fuentes consultadas:**\n"
                for f in resultado["fuentes"]:
                    fuentes_txt += f"• {f['ley']}"
                    if f.get("articulo"):
                        fuentes_txt += f" — {f['articulo']}"
                    fuentes_txt += "\n"
                respuesta += fuentes_txt

            if restantes == 0:
                respuesta += (
                    "\n\n---\n💡 Has usado tu consulta gratuita del día. "
                    "Vuelve mañana o visita lexjal.com para acceso ilimitado."
                )

            return [types.TextContent(type="text", text=respuesta)]

        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=(
                        "Lo siento, ocurrió un error procesando tu consulta. "
                        f"Por favor intenta de nuevo en unos momentos. (Error: {str(e)[:100]})"
                    ),
                )
            ]

    # ── Herramienta: estado_consultas ─────────────────────────────────────────
    elif name == "estado_consultas":
        user_key = f"mcp:{arguments.get('user_identifier', 'anonymous')}"
        limiter = get_rate_limiter()
        realizadas = await limiter.consultas_hoy(user_key)
        restantes = await limiter.consultas_restantes(user_key)

        estado = (
            f"📊 **Estado de consultas LexJal**\n"
            f"• Realizadas hoy: {realizadas}\n"
            f"• Consultas restantes: {restantes}\n"
            f"• Límite diario (plan gratuito): {settings.free_daily_limit}\n"
        )
        if restantes > 0:
            estado += "\n✅ Puedes realizar una consulta ahora."
        else:
            estado += "\n⚠️ Has alcanzado tu límite diario. Vuelve mañana."

        return [types.TextContent(type="text", text=estado)]

    else:
        raise ValueError(f"Herramienta desconocida: {name}")


async def main():
    """Punto de entrada del servidor MCP (modo stdio para Claude.ai)."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="lexjal",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
