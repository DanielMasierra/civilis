"""
Civilis — Router de consultas
Endpoints para interactuar con el agente jurídico.
"""
import json
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from backend.api.schemas import ConsultaRequest, ConsultaResponse, FuenteJuridica
from backend.agent.agent import get_agent
from backend.agent.prompts import LIMIT_REACHED_MESSAGE, WELCOME_MESSAGE
from backend.middleware.rate_limiter import get_rate_limiter, get_user_key
from backend.db.database import get_db
from backend.db.models import Consulta, EstadoConsulta
from backend.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/consulta", tags=["consulta"])


def _get_client_ip(request: Request) -> str:
    """Extrae la IP real del cliente (considera proxies)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_current_user_id(request: Request) -> Optional[str]:
    """Extrae el user_id del token JWT si está presente (para auth futura)."""
    # TODO: implementar extracción JWT completa en siguiente iteración
    return getattr(request.state, "user_id", None)


@router.get("/bienvenida")
async def bienvenida():
    """Mensaje de bienvenida para mostrar al abrir el chat."""
    return {"mensaje": WELCOME_MESSAGE}


@router.post("/", response_model=ConsultaResponse)
async def hacer_consulta(
    body: ConsultaRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint principal: procesa una consulta jurídica civil.

    - Verifica el límite de 1 consulta gratuita/día.
    - Recupera artículos legales relevantes (RAG).
    - Consulta a Claude con el contexto legal.
    - Persiste la consulta en la base de datos.
    - Retorna respuesta con fuentes citadas.
    """
    ip = _get_client_ip(request)
    user_id = _get_current_user_id(request)
    user_key = get_user_key(ip, user_id)
    limiter = get_rate_limiter()

    # ── Verificar límite diario ──────────────────────────────────────────────
    puede = await limiter.puede_consultar(user_key)
    if not puede:
        restantes = await limiter.consultas_restantes(user_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "mensaje": LIMIT_REACHED_MESSAGE,
                "consultas_restantes": restantes,
                "tipo": "limite_diario_alcanzado",
            },
        )

    # ── Persistir consulta (estado: procesando) ──────────────────────────────
    consulta_db = Consulta(
        usuario_id=user_id,
        session_key=user_key,
        pregunta=body.pregunta,
        canal=body.canal,
        ip_address=ip,
        estado=EstadoConsulta.procesando,
        es_consulta_gratuita=True,
    )
    db.add(consulta_db)
    await db.flush()  # Obtener ID sin hacer commit

    # ── Llamar al agente ─────────────────────────────────────────────────────
    agent = get_agent()
    try:
        resultado = await agent.consultar(
            pregunta=body.pregunta,
            historial=body.historial,
        )

        # Actualizar registro con la respuesta
        consulta_db.respuesta = resultado["respuesta"]
        consulta_db.contexto_recuperado = resultado["contexto_recuperado"]
        consulta_db.fuentes = json.dumps(resultado["fuentes"], ensure_ascii=False)
        consulta_db.tokens_entrada = resultado["tokens_entrada"]
        consulta_db.tokens_salida = resultado["tokens_salida"]
        consulta_db.tiempo_respuesta_ms = resultado["tiempo_respuesta_ms"]
        consulta_db.estado = EstadoConsulta.completada

        # Registrar en rate limiter
        await limiter.registrar_consulta(user_key)
        restantes = await limiter.consultas_restantes(user_key)

        return ConsultaResponse(
            id=str(consulta_db.id),
            respuesta=resultado["respuesta"],
            fuentes=[FuenteJuridica(**f) for f in resultado["fuentes"]],
            tokens_usados=resultado["tokens_entrada"] + resultado["tokens_salida"],
            tiempo_ms=resultado["tiempo_respuesta_ms"],
            consultas_restantes=restantes,
            advertencia_limite=(restantes == 0),
        )

    except ValueError as e:
        consulta_db.estado = EstadoConsulta.error
        await db.commit()
        if "sin_creditos" in str(e):
            raise HTTPException(
                status_code=503,
                detail="sin_creditos",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error procesando tu consulta. Por favor intenta de nuevo.",
        )
    except Exception as e:
        consulta_db.estado = EstadoConsulta.error
        await db.commit()
        logger.error(f"Error en consulta: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error procesando tu consulta. Por favor intenta de nuevo.",
        )


@router.post("/stream")
async def hacer_consulta_stream(
    body: ConsultaRequest,
    request: Request,
):
    """
    Versión streaming de la consulta.
    Devuelve Server-Sent Events (SSE) para mostrar la respuesta progresivamente.

    Formato de eventos:
      data: {"type": "sources", "sources": [...]}
      data: {"type": "token", "content": "..."}
      data: {"type": "done"}
    """
    ip = _get_client_ip(request)
    user_id = _get_current_user_id(request)
    user_key = get_user_key(ip, user_id)
    limiter = get_rate_limiter()

    # Verificar límite
    puede = await limiter.puede_consultar(user_key)
    if not puede:
        async def limite_stream():
            yield f"data: {json.dumps({'type': 'error', 'mensaje': LIMIT_REACHED_MESSAGE})}\n\n"
        return StreamingResponse(limite_stream(), media_type="text/event-stream")

    agent = get_agent()
    await limiter.registrar_consulta(user_key)

    return StreamingResponse(
        agent.consultar_stream(body.pregunta, body.historial),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Para Nginx
        },
    )


@router.get("/estado")
async def estado_usuario(request: Request):
    """Retorna el estado de uso diario del usuario (anónimo o autenticado)."""
    ip = _get_client_ip(request)
    user_id = _get_current_user_id(request)
    user_key = get_user_key(ip, user_id)
    limiter = get_rate_limiter()

    realizadas = await limiter.consultas_hoy(user_key)
    restantes = await limiter.consultas_restantes(user_key)

    return {
        "consultas_hoy": realizadas,
        "consultas_restantes": restantes,
        "limite_diario": settings.free_daily_limit,
        "puede_consultar": restantes > 0,
    }
