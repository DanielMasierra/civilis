#!/bin/bash
# ============================================================
# LexJal — Script de despliegue en VPS Hetzner
# Compatible con Ubuntu 24.04 LTS
#
# Uso:
#   ./scripts/deploy.sh          # Primer despliegue
#   ./scripts/deploy.sh update   # Actualizar sin perder datos
# ============================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[LexJal]${NC} $1"; }
warn() { echo -e "${YELLOW}[AVISO]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

MODE="${1:-install}"

# ── Verificaciones previas ────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || error "Ejecuta como root: sudo ./scripts/deploy.sh"
command -v docker &>/dev/null || error "Docker no está instalado"
command -v git &>/dev/null || error "Git no está instalado"

# ── Variables de proyecto ─────────────────────────────────────────────────────
PROJECT_DIR="/opt/lexjal"
REPO_URL="${LEXJAL_REPO:-https://github.com/tu-usuario/lexjal.git}"
DOMAIN="${LEXJAL_DOMAIN:-lexjal.com}"

# ── Modo: primer despliegue ───────────────────────────────────────────────────
if [[ "$MODE" == "install" ]]; then

    log "🚀 Instalando LexJal en ${PROJECT_DIR}..."

    # Instalar Docker si no está
    if ! command -v docker &>/dev/null; then
        log "Instalando Docker..."
        curl -fsSL https://get.docker.com | sh
        systemctl enable --now docker
    fi

    # Instalar Docker Compose plugin
    apt-get install -y docker-compose-plugin 2>/dev/null || true

    # Clonar repositorio
    if [[ -d "$PROJECT_DIR" ]]; then
        warn "El directorio ya existe. Haciendo pull..."
        cd "$PROJECT_DIR" && git pull
    else
        git clone "$REPO_URL" "$PROJECT_DIR"
    fi

    cd "$PROJECT_DIR"

    # Verificar .env
    if [[ ! -f .env ]]; then
        cp .env.example .env
        error "Crea el archivo .env con tus credenciales: nano ${PROJECT_DIR}/.env"
    fi

    # Crear directorios necesarios
    mkdir -p legal_docs logs nginx/ssl

    # SSL con Certbot (solo si el dominio apunta al servidor)
    if command -v certbot &>/dev/null; then
        log "Generando certificado SSL para ${DOMAIN}..."
        certbot certonly --standalone \
            --non-interactive \
            --agree-tos \
            --email admin@${DOMAIN} \
            -d ${DOMAIN} \
            -d www.${DOMAIN} || warn "SSL falló — usa certificados manuales en nginx/ssl/"

        # Copiar certificados al directorio de Nginx
        cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem nginx/ssl/
        cp /etc/letsencrypt/live/${DOMAIN}/privkey.pem nginx/ssl/
    else
        warn "Certbot no instalado. Instala SSL manualmente."
        apt-get install -y certbot 2>/dev/null || true
    fi

    # Construir y levantar servicios
    log "Construyendo imágenes Docker..."
    docker compose build

    log "Levantando servicios..."
    docker compose up -d

    # Esperar a que la API esté lista
    log "Esperando a que la API esté lista..."
    for i in {1..30}; do
        if curl -sf http://localhost:8080/health &>/dev/null; then
            log "✅ API lista"
            break
        fi
        sleep 2
    done

    # Ingestar documentos legales si existen
    if ls legal_docs/*.pdf 1>/dev/null 2>&1; then
        log "Indexando documentos legales..."
        docker compose exec api python ingestion/ingest.py
    else
        warn "No hay PDFs en legal_docs/. Agrégalos y ejecuta:"
        warn "  docker compose exec api python ingestion/ingest.py --download"
    fi

    log "✅ LexJal instalado correctamente"
    log "🌐 API disponible en: https://${DOMAIN}/api/"
    log "📋 Docs (dev): https://${DOMAIN}/docs"

# ── Modo: actualización ───────────────────────────────────────────────────────
elif [[ "$MODE" == "update" ]]; then

    cd "$PROJECT_DIR"
    log "🔄 Actualizando LexJal..."

    git pull origin main

    log "Reconstruyendo imagen del API..."
    docker compose build api

    log "Reiniciando servicio API..."
    docker compose up -d --no-deps api

    log "✅ Actualización completada"
    docker compose ps

fi

# ── Estado final ──────────────────────────────────────────────────────────────
echo ""
log "Estado de los servicios:"
docker compose ps 2>/dev/null || true
