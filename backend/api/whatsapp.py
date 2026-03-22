"""
Civilis — Webhook de WhatsApp (Fase 2)
Integración con Meta Business API para recibir y responder mensajes de WhatsApp.

Activación: descomentar en main.py cuando se inicie la fase 2.

Requisitos:
  1. Cuenta verificada en Meta Business Suite
  2. Número de WhatsApp Business registrado
  3. Variables de entorno: META_VERIFY_TOKEN, WHATSAPP_PHONE_NUMBER_ID,
     META_APP_SECRET (para verificar firma de webhooks)
"""
import hashlib
import hmac
import json
from typing import Optional

import httpx
from fastapi import APIRouter, Request, HTTPException, Response
from loguru import logger

from backend.config import get_settings
from backend.agent.agent import get_agent
from backend.middleware.rate_limiter import get_rate_limiter, get_user_key
from backend.agent.prompts import LIMIT_REACHED_MESSAGE

settings = get_settings()
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

WHATSAPP_API_URL = "https://graph.facebook.com/v19.0"


# ── Verificación del webhook (requerida por Meta) ─────────────────────────────
@router.get("/webhook")
async def verify_webhook(request: Request):
    """
    Meta verifica el webhook enviando un GET con un challenge.
    Debemos responder con el challenge para confirmar la suscripción.
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.meta_verify_token:
        logger.info("Webhook de WhatsApp verificado correctamente")
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Token de verificación inválido")


# ── Recepción de mensajes ─────────────────────────────────────────────────────
@router.post("/webhook")
async def receive_message(request: Request):
    """
    Recibe mensajes entrantes de WhatsApp y responde con el agente Civilis.
    Meta envía eventos POST con los mensajes de los usuarios.
    """
    # Verificar firma de Meta (seguridad)
    body_bytes = await request.body()
    _verify_meta_signature(request, body_bytes)

    try:
        data = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON inválido")

    # Procesar eventos de mensajes
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue

            value = change.get("value", {})
            messages = value.get("messages", [])

            for message in messages:
                await _process_whatsapp_message(message, value)

    # Meta requiere respuesta 200 inmediata
    return {"status": "ok"}


async def _process_whatsapp_message(message: dict, value: dict):
    """Procesa un mensaje individual de WhatsApp."""
    msg_type = message.get("type")
    phone = message.get("from")  # Número de teléfono del usuario
    msg_id = message.get("id")

    if msg_type != "text":
        await _send_whatsapp_message(
            phone,
            "Solo puedo procesar mensajes de texto por ahora. Por favor escríbeme tu consulta jurídica.",
        )
        return

    pregunta = message.get("text", {}).get("body", "").strip()
    if not pregunta:
        return

    logger.info(f"WhatsApp mensaje de {phone}: {pregunta[:80]}")

    # Rate limit por número de teléfono
    user_key = get_user_key(ip=phone, user_id=f"wa:{phone}")
    limiter = get_rate_limiter()

    puede = await limiter.puede_consultar(user_key)
    if not puede:
        await _send_whatsapp_message(phone, _format_whatsapp(LIMIT_REACHED_MESSAGE))
        return

    # Indicador "escribiendo..." en WhatsApp
    await _send_typing_indicator(phone)

    # Llamar al agente
    agent = get_agent()
    try:
        resultado = await agent.consultar(pregunta=pregunta)
        await limiter.registrar_consulta(user_key)

        # Formatear respuesta para WhatsApp (sin Markdown complejo)
        respuesta = _format_whatsapp(resultado["respuesta"])

        # Agregar fuentes al final
        if resultado["fuentes"]:
            respuesta += "\n\n📚 *Fuentes:*"
            for f in resultado["fuentes"]:
                respuesta += f"\n• {f['ley']}"
                if f.get("articulo"):
                    respuesta += f" — {f['articulo']}"

        # Agregar alerta de consultas restantes
        restantes = await limiter.consultas_restantes(user_key)
        if restantes == 0:
            respuesta += (
                "\n\n⚠️ Esta fue tu consulta gratuita del día. "
                "Vuelve mañana o visita civilis.com para acceso ilimitado."
            )

        await _send_whatsapp_message(phone, respuesta)

    except Exception as e:
        logger.error(f"Error procesando mensaje de WhatsApp: {e}")
        await _send_whatsapp_message(
            phone,
            "Lo siento, ocurrió un error procesando tu consulta. Por favor intenta de nuevo en unos momentos.",
        )


async def _send_whatsapp_message(phone: str, text: str):
    """Envía un mensaje de texto al usuario de WhatsApp."""
    # WhatsApp limita mensajes a 4096 caracteres
    if len(text) > 4096:
        text = text[:4090] + "..."

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text, "preview_url": False},
    }

    headers = {
        "Authorization": f"Bearer {settings.meta_verify_token}",
        "Content-Type": "application/json",
    }

    url = f"{WHATSAPP_API_URL}/{settings.whatsapp_phone_number_id}/messages"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code != 200:
            logger.error(f"Error enviando mensaje WhatsApp: {response.text}")


async def _send_typing_indicator(phone: str):
    """Envía indicador de 'escribiendo...' (solo disponible en algunas cuentas)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "reaction",
        "reaction": {"message_id": "none", "emoji": "⚖️"},
    }
    # Este endpoint puede no estar disponible en todas las cuentas
    # Se omite el error silenciosamente
    try:
        headers = {"Authorization": f"Bearer {settings.meta_verify_token}"}
        url = f"{WHATSAPP_API_URL}/{settings.whatsapp_phone_number_id}/messages"
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, headers=headers, timeout=5)
    except Exception:
        pass


def _verify_meta_signature(request: Request, body: bytes):
    """Verifica que el webhook viene realmente de Meta usando HMAC-SHA256."""
    signature = request.headers.get("x-hub-signature-256", "")
    if not signature.startswith("sha256="):
        return  # En desarrollo, omitir verificación

    app_secret = settings.meta_app_secret if hasattr(settings, "meta_app_secret") else ""
    if not app_secret:
        return

    expected = "sha256=" + hmac.new(
        app_secret.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Firma inválida de Meta")


def _format_whatsapp(text: str) -> str:
    """Convierte Markdown básico a formato WhatsApp."""
    # WhatsApp usa *negrita*, _cursiva_, ~tachado~, `monoespaciado`
    # Elimina ** para * (WhatsApp solo usa un asterisco)
    text = text.replace("**", "*")
    # Elimina # de headers (WhatsApp no los soporta)
    import re
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    return text
