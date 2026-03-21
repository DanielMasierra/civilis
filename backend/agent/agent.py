"""
LexJal — Agente principal
Orquesta el flujo: consulta → RAG → Claude → respuesta citada.
"""
import time
import json
from typing import AsyncGenerator, Optional
from loguru import logger

import anthropic

from backend.config import get_settings
from backend.agent.prompts import SYSTEM_PROMPT, LIMIT_REACHED_MESSAGE
from backend.agent.rag import get_rag

settings = get_settings()


class LexJalAgent:
    """
    Agente de orientación jurídica civil.

    Flujo:
      1. Recibe pregunta del usuario.
      2. Recupera artículos relevantes del corpus legal (RAG).
      3. Construye el prompt con el contexto recuperado.
      4. Llama a Claude con instrucciones estrictas anti-alucinación.
      5. Devuelve la respuesta con las fuentes citadas.
    """

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._rag = get_rag()

    async def consultar(
        self,
        pregunta: str,
        historial: Optional[list[dict]] = None,
    ) -> dict:
        """
        Procesa una consulta completa.

        Args:
            pregunta: Pregunta del usuario en lenguaje natural.
            historial: Mensajes anteriores de la conversación (opcional).

        Returns:
            Dict con respuesta, fuentes, tokens usados y tiempo de respuesta.
        """
        start_ms = int(time.time() * 1000)

        # 1. Recuperar contexto legal relevante
        context, sources = await self._rag.retrieve(pregunta)

        if not context:
            context = "No se encontró información específica en el corpus legal disponible."
            logger.warning(f"Sin contexto RAG para: {pregunta[:80]}")

        # 2. Construir el system prompt con el contexto
        system = SYSTEM_PROMPT.format(context=context, question="")

        # 3. Preparar mensajes
        messages = []

        # Incluir historial si existe (conversación continua)
        if historial:
            for msg in historial[-6:]:  # Últimos 3 turnos (6 mensajes)
                if msg.get("role") in ("user", "assistant"):
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                    })

        # Mensaje actual del usuario
        messages.append({"role": "user", "content": pregunta})

        # 4. Llamar a Claude
        try:
            response = await self._client.messages.create(
                model=settings.claude_model,
                max_tokens=2048,
                system=system,
                messages=messages,
                temperature=0.1,  # Baja temperatura = respuestas más precisas y consistentes
            )

            respuesta_texto = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens

        except anthropic.APIError as e:
            logger.error(f"Error API Anthropic: {e}")
            raise

        elapsed_ms = int(time.time() * 1000) - start_ms

        return {
            "respuesta": respuesta_texto,
            "fuentes": sources,
            "contexto_recuperado": context,
            "tokens_entrada": tokens_in,
            "tokens_salida": tokens_out,
            "tiempo_respuesta_ms": elapsed_ms,
        }

    async def consultar_stream(
        self,
        pregunta: str,
        historial: Optional[list[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Versión streaming para respuesta en tiempo real.
        Útil para la interfaz web — el usuario ve la respuesta aparecer progresivamente.
        """
        # Recuperar contexto
        context, sources = await self._rag.retrieve(pregunta)
        if not context:
            context = "No se encontró información específica en el corpus legal disponible."

        system = SYSTEM_PROMPT.format(context=context, question="")

        messages = []
        if historial:
            for msg in historial[-6:]:
                if msg.get("role") in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": pregunta})

        # Emite las fuentes primero como evento SSE especial
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"

        # Streaming de la respuesta
        async with self._client.messages.stream(
            model=settings.claude_model,
            max_tokens=2048,
            system=system,
            messages=messages,
            temperature=0.1,
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"


# Singleton global
_agent_instance: Optional[LexJalAgent] = None


def get_agent() -> LexJalAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = LexJalAgent()
    return _agent_instance
