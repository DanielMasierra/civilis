"""Script de ingesta de documentos legales en ChromaDB."""
import sys
from loguru import logger
from backend.agent.rag import get_rag

def main():
    logger.info("🚀 Iniciando ingesta de documentos legales...")
    rag = get_rag()
    total = rag.ingest_documents("/app/legal_docs")
    if total > 0:
        logger.success(f"✅ Ingesta completada: {total} chunks indexados")
        stats = rag.collection_stats()
        logger.info(f"📊 Stats: {stats}")
    else:
        logger.warning("⚠️ No se indexaron documentos")
    return total

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result > 0 else 1)
