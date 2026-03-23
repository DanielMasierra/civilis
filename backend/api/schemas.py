"""
Civilis — Schemas Pydantic
Define los modelos de entrada y salida de la API REST.
"""
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ─── Consulta ─────────────────────────────────────────────────────────────────

class ConsultaRequest(BaseModel):
    """Petición de consulta jurídica."""
    pregunta: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Pregunta o descripción de la situación jurídica",
        examples=["¿Mi casero puede aumentar la renta sin avisarme?"],
    )
    historial: Optional[list[dict]] = Field(
        default=None,
        description="Historial de mensajes para conversaciones continuas",
    )
    usuario_id: Optional[str] = Field(
        default=None,
        description="Email o identificador del usuario",
    )
    canal: str = Field(
        default="web",
        description="Canal de origen: web | mcp | whatsapp",
    )


class FuenteJuridica(BaseModel):
    """Fuente legal citada en la respuesta."""
    ley: str
    articulo: str
    fragmento: str


class ConsultaResponse(BaseModel):
    """Respuesta de la consulta jurídica."""
    id: Optional[str] = None
    respuesta: str
    fuentes: list[FuenteJuridica] = []
    tokens_usados: int = 0
    tiempo_ms: int = 0
    consultas_restantes: int = 0
    advertencia_limite: bool = False

    class Config:
        from_attributes = True


class ConsultaHistorial(BaseModel):
    """Item del historial de consultas del usuario."""
    id: str
    pregunta: str
    respuesta: str
    creado_en: datetime
    fuentes: list[FuenteJuridica] = []

    class Config:
        from_attributes = True


# ─── Usuario / Auth ───────────────────────────────────────────────────────────

class RegistroRequest(BaseModel):
    """Datos para registro de usuario."""
    email: EmailStr
    nombre: Optional[str] = None
    password: str = Field(..., min_length=8)


class LoginRequest(BaseModel):
    """Credenciales de inicio de sesión."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token JWT de acceso."""
    access_token: str
    token_type: str = "bearer"
    expira_en: int  # segundos


class UsuarioResponse(BaseModel):
    """Perfil del usuario autenticado."""
    id: str
    email: str
    nombre: Optional[str] = None
    plan: str
    suscripcion_activa: bool
    consultas_hoy: int
    limite_diario: int
    consultas_restantes: int

    class Config:
        from_attributes = True


# ─── Admin / Corpus ───────────────────────────────────────────────────────────

class CorpusStatsResponse(BaseModel):
    """Estadísticas del corpus legal indexado."""
    total_chunks: int
    coleccion: str


class IngestResponse(BaseModel):
    """Resultado de la ingesta de documentos."""
    chunks_indexados: int
    mensaje: str


# ─── Pagos (Fase 3) ──────────────────────────────────────────────────────────

class PagoIntentRequest(BaseModel):
    """Solicitud de intención de pago."""
    plan: str = Field(..., description="basico | profesional")


class PagoIntentResponse(BaseModel):
    """Client secret de Stripe para completar el pago."""
    client_secret: str
    monto: int   # en centavos MXN
    moneda: str = "mxn"
