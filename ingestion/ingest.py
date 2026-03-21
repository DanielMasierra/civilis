"""
LexJal — Script de ingesta de documentos legales
Descarga los PDFs de fuentes oficiales y los indexa en ChromaDB.

Uso:
  python ingestion/ingest.py                    # Indexa los que ya están en legal_docs/
  python ingestion/ingest.py --download         # Descarga + indexa
  python ingestion/ingest.py --stats            # Solo muestra estadísticas
"""
import sys
import os
import argparse
from pathlib import Path

# Añade el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger


# ─── Fuentes oficiales de documentos ──────────────────────────────────────────
# Estas son las URLs oficiales de los documentos legales.
# Si cambian, actualizar aquí.
LEGAL_SOURCES = {
    "codigo_civil_jalisco.pdf": {
        "url": "https://congresoweb.congresojal.gob.mx/Sistemas/Legislacion/legislacion/Leyes/Código Civil del Estado de Jalisco.pdf",
        "desc": "Código Civil del Estado de Jalisco",
        "prioritario": True,
    },
    "codigo_procedimientos_civiles_jalisco.pdf": {
        "url": "https://congresoweb.congresojal.gob.mx/Sistemas/Legislacion/legislacion/Leyes/Código de Procedimientos Civiles del Estado de Jalisco.pdf",
        "desc": "Código de Procedimientos Civiles de Jalisco",
        "prioritario": True,
    },
    "codigo_civil_federal.pdf": {
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/2_110121.pdf",
        "desc": "Código Civil Federal",
        "prioritario": True,
    },
    "ley_familia_jalisco.pdf": {
        "url": "https://congresoweb.congresojal.gob.mx/Sistemas/Legislacion/legislacion/Leyes/Código Familiar del Estado de Jalisco.pdf",
        "desc": "Código Familiar del Estado de Jalisco",
        "prioritario": True,
    },
    "ley_registro_civil_jalisco.pdf": {
        "url": "https://congresoweb.congresojal.gob.mx/Sistemas/Legislacion/legislacion/Leyes/Ley del Registro Civil del Estado de Jalisco.pdf",
        "desc": "Ley del Registro Civil de Jalisco",
        "prioritario": False,
    },
    "ley_notariado_jalisco.pdf": {
        "url": "https://congresoweb.congresojal.gob.mx/Sistemas/Legislacion/legislacion/Leyes/Ley del Notariado del Estado de Jalisco.pdf",
        "desc": "Ley del Notariado de Jalisco",
        "prioritario": False,
    },
    "ley_arrendamiento_jalisco.pdf": {
        "url": "https://congresoweb.congresojal.gob.mx/Sistemas/Legislacion/legislacion/Leyes/Ley de Arrendamiento Inmobiliario para el Estado de Jalisco.pdf",
        "desc": "Ley de Arrendamiento Inmobiliario de Jalisco",
        "prioritario": False,
    },
}

DOCS_DIR = Path("./legal_docs")


def download_docs(solo_prioritarios: bool = False):
    """Descarga los PDFs de fuentes oficiales."""
    import requests
    from urllib.parse import quote

    DOCS_DIR.mkdir(exist_ok=True)
    descargados = 0
    errores = 0

    for filename, info in LEGAL_SOURCES.items():
        if solo_prioritarios and not info["prioritario"]:
            continue

        dest = DOCS_DIR / filename
        if dest.exists():
            logger.info(f"Ya existe: {filename} — omitiendo")
            continue

        logger.info(f"Descargando: {info['desc']}...")
        try:
            # Algunas URLs tienen caracteres especiales
            url = info["url"]
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; LexJal/1.0; +https://lexjal.com)",
            }
            response = requests.get(url, headers=headers, timeout=60, stream=True)
            response.raise_for_status()

            with open(dest, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            size_kb = dest.stat().st_size / 1024
            logger.success(f"✅ {filename} ({size_kb:.0f} KB)")
            descargados += 1

        except Exception as e:
            logger.error(f"❌ Error descargando {filename}: {e}")
            logger.info(f"   → Descarga manual: {info['url']}")
            errores += 1

    logger.info(f"\nDescarga completada: {descargados} OK, {errores} errores")
    if errores > 0:
        logger.warning(
            "Para los archivos con error, descárgalos manualmente desde:\n"
            "  • Jalisco: https://congresoweb.congresojal.gob.mx\n"
            "  • Federal: https://www.diputados.gob.mx/LeyesBiblio/\n"
            f"Y colócalos en: {DOCS_DIR.absolute()}"
        )


def run_ingestion():
    """Ejecuta la ingesta de documentos en ChromaDB."""
    from backend.agent.rag import get_rag

    pdfs = list(DOCS_DIR.glob("*.pdf"))
    if not pdfs:
        logger.error(
            f"No se encontraron PDFs en {DOCS_DIR.absolute()}\n"
            "Ejecuta con --download para descargarlos automáticamente,\n"
            "o coloca los PDFs manualmente en la carpeta legal_docs/"
        )
        sys.exit(1)

    logger.info(f"Iniciando ingesta de {len(pdfs)} documentos...")
    for pdf in pdfs:
        logger.info(f"  • {pdf.name}")

    rag = get_rag()
    total = rag.ingest_documents(docs_path=str(DOCS_DIR))

    if total > 0:
        logger.success(f"\n✅ Ingesta exitosa: {total} fragmentos indexados en ChromaDB")
    else:
        logger.warning("No se indexaron fragmentos. Revisa los logs anteriores.")


def show_stats():
    """Muestra estadísticas del corpus indexado."""
    from backend.agent.rag import get_rag
    rag = get_rag()
    stats = rag.collection_stats()
    if "error" in stats:
        logger.error(f"Error obteniendo estadísticas: {stats['error']}")
    else:
        logger.info(f"Corpus LexJal:")
        logger.info(f"  Colección: {stats['coleccion']}")
        logger.info(f"  Fragmentos indexados: {stats['total_chunks']}")


def main():
    parser = argparse.ArgumentParser(
        description="LexJal — Ingesta de documentos legales"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Descargar PDFs de fuentes oficiales antes de indexar",
    )
    parser.add_argument(
        "--solo-prioritarios",
        action="store_true",
        help="Solo descargar los documentos prioritarios (Códigos Civiles)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Mostrar estadísticas del corpus sin indexar",
    )

    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    if args.download:
        download_docs(solo_prioritarios=args.solo_prioritarios)

    run_ingestion()


if __name__ == "__main__":
    main()
