"""
Civilis — Modelos de base de datos
Define las tablas: usuarios, consultas y suscripciones.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    ForeignKey, Text, Enum as SAEnum, Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class PlanTipo(str, enum.Enum):
    gratuito = "gratuito"
    basico = "basico"       # Fase 3: plan pagado
    profesional = "profesional"  # Fase 3


class EstadoConsulta(str, enum.Enum):
    procesando = "procesando"
    completada = "completada"
    error = "error"


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    nombre = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=True)  # Null si login con OAuth

    # Plan y pagos (fase 3)
    plan = Column(SAEnum(PlanTipo), default=PlanTipo.gratuito, nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    suscripcion_activa = Column(Boolean, default=False)

    # Metadatos
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    consultas = relationship("Consulta", back_populates="usuario", lazy="dynamic")

    def __repr__(self):
        return f"<Usuario {self.email} plan={self.plan}>"


class Consulta(Base):
    __tablename__ = "consultas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)

    # Para usuarios anónimos (por IP, fase inicial)
    session_key = Column(String(255), nullable=True, index=True)

    # Contenido de la consulta
    pregunta = Column(Text, nullable=False)
    respuesta = Column(Text, nullable=True)
    contexto_recuperado = Column(Text, nullable=True)  # Artículos usados como fuente
    fuentes = Column(Text, nullable=True)              # JSON con leyes citadas

    # Métricas
    tokens_entrada = Column(Integer, nullable=True)
    tokens_salida = Column(Integer, nullable=True)
    tiempo_respuesta_ms = Column(Integer, nullable=True)

    # Estado
    estado = Column(SAEnum(EstadoConsulta), default=EstadoConsulta.procesando)
    es_consulta_gratuita = Column(Boolean, default=True)

    # Metadatos
    canal = Column(String(50), default="web")  # web | mcp | whatsapp
    ip_address = Column(String(45), nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    # Relación
    usuario = relationship("Usuario", back_populates="consultas")

    def __repr__(self):
        return f"<Consulta {self.id} estado={self.estado}>"


class Pago(Base):
    """Fase 3 — registro de transacciones de pago."""
    __tablename__ = "pagos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    stripe_payment_intent_id = Column(String(255), unique=True, nullable=False)
    monto = Column(Float, nullable=False)
    moneda = Column(String(10), default="mxn")
    estado = Column(String(50), nullable=False)  # succeeded | failed | pending
    creado_en = Column(DateTime, default=datetime.utcnow)
