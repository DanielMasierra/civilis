"""
LexJal — Aplicación principal FastAPI
Punto de entrada del backend. Registra routers, middleware y eventos.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from backend.config import get_settings
from backend.db.database import create_tables
from backend.api.consultas import router as consultas_router
from backend.api.admin import router as admin_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eventos de inicio y cierre de la aplicación."""
    logger.info("🚀 Iniciando LexJal API...")

    # Crear tablas en la base de datos
    try:
        await create_tables()
        logger.info("✅ Base de datos lista")
    except Exception as e:
        logger.warning(f"No se pudieron crear las tablas (puede que ya existan): {e}")

    # Pre-cargar el modelo de embeddings para evitar demora en primera consulta
    try:
        from backend.agent.rag import get_rag
        rag = get_rag()
        rag._get_embeddings()
        logger.info("✅ Modelo de embeddings cargado")
    except Exception as e:
        logger.warning(f"No se pudo pre-cargar embeddings: {e}")

    logger.info("✅ LexJal API lista para recibir consultas")
    yield

    logger.info("👋 Cerrando LexJal API...")


app = FastAPI(
    title="LexJal API",
    description=(
        "Agente de orientación jurídica civil para Jalisco y México. "
        "Acceso gratuito a 1 consulta diaria basada en el corpus legal oficial."
    ),
    version="1.0.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(consultas_router)
app.include_router(admin_router)


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["sistema"])
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.0",
        "agente": "LexJal",
        "entorno": settings.environment,
    }


# ─── Handler de errores globales ──────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Error no manejado: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor. Por favor intenta de nuevo."},
    )
