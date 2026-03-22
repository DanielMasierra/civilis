"""
Civilis — Integración de pagos Stripe (Fase 3)
Maneja suscripciones, pagos únicos y webhooks de Stripe.

Planes:
  - Básico:       MXN 99/mes  → 30 consultas/día
  - Profesional:  MXN 299/mes → ilimitado

Activación: registrar el router en main.py cuando inicie la fase 3.
"""
import json
from typing import Optional

import stripe
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from backend.config import get_settings
from backend.db.database import get_db
from backend.db.models import Usuario, Pago, PlanTipo
from backend.api.schemas import PagoIntentRequest, PagoIntentResponse

settings = get_settings()
stripe.api_key = settings.stripe_secret_key

router = APIRouter(prefix="/pagos", tags=["pagos"])

# ── Configuración de planes ────────────────────────────────────────────────────
PLANES = {
    "basico": {
        "nombre": "Civilis Básico",
        "monto_mxn": 9900,       # En centavos: MXN 99.00
        "consultas_dia": 30,
        "descripcion": "30 consultas jurídicas al día",
        "stripe_price_id": "",   # Crear en Stripe Dashboard y pegar aquí
    },
    "profesional": {
        "nombre": "Civilis Profesional",
        "monto_mxn": 29900,      # MXN 299.00
        "consultas_dia": -1,     # -1 = ilimitado
        "descripcion": "Consultas ilimitadas + prioridad de respuesta",
        "stripe_price_id": "",   # Crear en Stripe Dashboard y pegar aquí
    },
}


# ── Crear intención de pago ────────────────────────────────────────────────────
@router.post("/intent", response_model=PagoIntentResponse)
async def crear_pago_intent(
    body: PagoIntentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Crea un PaymentIntent de Stripe para iniciar el flujo de pago.
    El frontend completa el pago con el client_secret usando Stripe Elements.
    """
    if body.plan not in PLANES:
        raise HTTPException(status_code=400, detail=f"Plan inválido: {body.plan}")

    plan = PLANES[body.plan]
    user_id = getattr(request.state, "user_id", None)

    # Obtener o crear cliente en Stripe
    stripe_customer_id = None
    if user_id:
        result = await db.execute(select(Usuario).where(Usuario.id == user_id))
        usuario = result.scalar_one_or_none()
        if usuario:
            if not usuario.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=usuario.email,
                    name=usuario.nombre or "",
                    metadata={"user_id": str(user_id)},
                )
                usuario.stripe_customer_id = customer.id
                stripe_customer_id = customer.id
            else:
                stripe_customer_id = usuario.stripe_customer_id

    # Crear PaymentIntent
    intent_params = {
        "amount": plan["monto_mxn"],
        "currency": "mxn",
        "description": f"Civilis — {plan['nombre']}",
        "metadata": {
            "plan": body.plan,
            "user_id": str(user_id) if user_id else "anonymous",
        },
        "automatic_payment_methods": {"enabled": True},
    }
    if stripe_customer_id:
        intent_params["customer"] = stripe_customer_id

    try:
        intent = stripe.PaymentIntent.create(**intent_params)
        return PagoIntentResponse(
            client_secret=intent.client_secret,
            monto=plan["monto_mxn"],
        )
    except stripe.StripeError as e:
        logger.error(f"Error Stripe: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar el pago")


# ── Webhook de Stripe ─────────────────────────────────────────────────────────
@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Recibe eventos de Stripe para actualizar el plan del usuario
    cuando un pago se completa exitosamente.

    Eventos manejados:
      - payment_intent.succeeded → activar suscripción
      - customer.subscription.deleted → desactivar suscripción
    """
    body = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            body, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma de webhook inválida")

    logger.info(f"Evento Stripe: {event['type']}")

    if event["type"] == "payment_intent.succeeded":
        await _handle_payment_succeeded(event["data"]["object"], db)

    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        await _handle_subscription_cancelled(event["data"]["object"], db)

    return {"received": True}


async def _handle_payment_succeeded(payment_intent: dict, db: AsyncSession):
    """Activa el plan del usuario cuando el pago se confirma."""
    metadata = payment_intent.get("metadata", {})
    user_id = metadata.get("user_id")
    plan_nombre = metadata.get("plan")

    if not user_id or user_id == "anonymous" or plan_nombre not in PLANES:
        return

    result = await db.execute(select(Usuario).where(Usuario.id == user_id))
    usuario = result.scalar_one_or_none()
    if not usuario:
        return

    # Actualizar plan del usuario
    plan_enum = PlanTipo.basico if plan_nombre == "basico" else PlanTipo.profesional
    usuario.plan = plan_enum
    usuario.suscripcion_activa = True

    # Registrar pago
    pago = Pago(
        usuario_id=usuario.id,
        stripe_payment_intent_id=payment_intent["id"],
        monto=payment_intent["amount"] / 100,
        moneda=payment_intent["currency"],
        estado="succeeded",
    )
    db.add(pago)

    # Actualizar límite en Redis
    plan_config = PLANES[plan_nombre]
    consultas_dia = plan_config["consultas_dia"]
    logger.info(
        f"Plan {plan_nombre} activado para usuario {user_id}. "
        f"Consultas/día: {'ilimitadas' if consultas_dia == -1 else consultas_dia}"
    )


async def _handle_subscription_cancelled(subscription: dict, db: AsyncSession):
    """Regresa al usuario al plan gratuito cuando cancela."""
    customer_id = subscription.get("customer")
    if not customer_id:
        return

    result = await db.execute(
        select(Usuario).where(Usuario.stripe_customer_id == customer_id)
    )
    usuario = result.scalar_one_or_none()
    if not usuario:
        return

    usuario.plan = PlanTipo.gratuito
    usuario.suscripcion_activa = False
    logger.info(f"Suscripción cancelada para usuario {usuario.email}")


@router.get("/planes")
async def listar_planes():
    """Retorna los planes disponibles (sin datos sensibles de Stripe)."""
    return [
        {
            "id": plan_id,
            "nombre": plan["nombre"],
            "monto_mxn": plan["monto_mxn"] / 100,
            "consultas_dia": plan["consultas_dia"],
            "descripcion": plan["descripcion"],
        }
        for plan_id, plan in PLANES.items()
    ]
