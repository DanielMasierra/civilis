# ============================================================
# LexJal — Dockerfile del backend
# Multi-stage build para imagen ligera en producción
# ============================================================

FROM python:3.12-slim AS base

# Variables de entorno del sistema
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias del sistema (necesarias para psycopg2, unstructured, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Instalar dependencias Python ──────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Pre-descargar el modelo de embeddings en tiempo de build
# (evita descarga en primer arranque que tarda varios minutos)
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/paraphrase-multilingual-mpnet-base-v2')"

# ── Copiar código fuente ───────────────────────────────────────────────────────
COPY . .

# Crear directorio de logs
RUN mkdir -p /app/logs /app/legal_docs

# Usuario no-root por seguridad
RUN useradd -m -u 1000 lexjal && \
    chown -R lexjal:lexjal /app
USER lexjal

# ── Healthcheck interno ────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# ── Punto de entrada ───────────────────────────────────────────────────────────
EXPOSE 8080

CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "2", \
     "--log-level", "info"]
