"""
LexJal — Router de administración
Endpoints para gestión del corpus legal y estadísticas del sistema.
Protegidos por API key de administrador.
"""
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Depends
from loguru import logger

from backend.agent.rag import get_rag
from backend.api.schemas import CorpusStatsResponse, IngestResponse
from backend.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/admin", tags=["administración"])


def _verify_admin_key(x_admin_key: str = Header(...)):
    """Verifica la API key de administrador."""
    admin_key = os.getenv("ADMIN_API_KEY", "")
    if not admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=403, detail="Acceso no autorizado")
    return True


@router.get("/corpus/stats", response_model=CorpusStatsResponse)
async def corpus_stats(_: bool = Depends(_verify_admin_key)):
    """Estadísticas del corpus legal indexado en ChromaDB."""
    rag = get_rag()
    stats = rag.collection_stats()
    if "error" in stats:
        raise HTTPException(status_code=503, detail=stats["error"])
    return CorpusStatsResponse(**stats)


@router.post("/corpus/ingest", response_model=IngestResponse)
async def ingest_docs(_: bool = Depends(_verify_admin_key)):
    """
    Indexa los PDFs del directorio legal_docs en ChromaDB.
    Los archivos deben estar en ./legal_docs/ con los nombres correctos.
    """
    rag = get_rag()
    try:
        total = rag.ingest_documents(docs_path="./legal_docs")
        return IngestResponse(
            chunks_indexados=total,
            mensaje=f"Ingesta completada: {total} fragmentos indexados en ChromaDB.",
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error en ingesta: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/corpus/upload", response_model=IngestResponse)
async def upload_and_ingest(
    files: list[UploadFile] = File(...),
    _: bool = Depends(_verify_admin_key),
):
    """
    Sube PDFs y los indexa directamente.
    Permite agregar nuevas leyes sin acceso SSH al servidor.
    """
    rag = get_rag()
    total = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        for file in files:
            if not file.filename.endswith(".pdf"):
                continue

            dest = Path(tmpdir) / file.filename
            content = await file.read()
            dest.write_bytes(content)
            logger.info(f"Archivo subido: {file.filename} ({len(content)/1024:.1f} KB)")

        try:
            total = rag.ingest_documents(docs_path=tmpdir)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return IngestResponse(
        chunks_indexados=total,
        mensaje=f"Se procesaron {len(files)} archivos: {total} fragmentos indexados.",
    )


@router.post("/rate-limit/reset/{user_key}")
async def reset_rate_limit(
    user_key: str,
    _: bool = Depends(_verify_admin_key),
):
    """Resetea el límite diario de un usuario específico (soporte técnico)."""
    from backend.middleware.rate_limiter import get_rate_limiter
    limiter = get_rate_limiter()
    await limiter.reset_usuario(user_key)
    return {"mensaje": f"Límite reseteado para: {user_key}"}
