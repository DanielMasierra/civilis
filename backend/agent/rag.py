"""
Civilis — RAG Pipeline
Carga documentos legales en ChromaDB y recupera los más relevantes
para cada consulta. Usa embeddings locales (sentence-transformers) para
evitar costos adicionales de API de embeddings.
"""
import os
from pathlib import Path
from typing import Optional
from loguru import logger

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from backend.config import get_settings

settings = get_settings()

# Modelo de embeddings: multilingüe, funciona muy bien en español, 100% local
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# Configuración de chunking para textos legales
# Los artículos son cortos pero densos — chunks medianos con superposición
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K_RESULTS = 6  # Documentos a recuperar por consulta


class LegalRAG:
    """
    RAG especializado en documentos jurídicos.
    Maneja la carga, indexación y recuperación de leyes.
    """

    def __init__(self):
        self._embeddings = None
        self._vectorstore = None
        self._retriever = None

    def _get_embeddings(self) -> HuggingFaceEmbeddings:
        """Inicializa el modelo de embeddings (se carga una sola vez)."""
        if self._embeddings is None:
            logger.info(f"Cargando modelo de embeddings: {EMBEDDING_MODEL}")
            self._embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self._embeddings

    def _get_chroma_client(self) -> chromadb.HttpClient:
        """Crea cliente de ChromaDB."""
        return chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def get_vectorstore(self) -> Chroma:
        """Obtiene o crea el vectorstore."""
        if self._vectorstore is None:
            client = self._get_chroma_client()
            self._vectorstore = Chroma(
                client=client,
                collection_name=settings.chroma_collection,
                embedding_function=self._get_embeddings(),
            )
            logger.info(f"Vectorstore listo: colección '{settings.chroma_collection}'")
        return self._vectorstore

    def get_retriever(self):
        """Obtiene el retriever configurado para consultas legales."""
        if self._retriever is None:
            vs = self.get_vectorstore()
            self._retriever = vs.as_retriever(
                search_type="mmr",  # Maximum Marginal Relevance — evita redundancia
                search_kwargs={
                    "k": TOP_K_RESULTS,
                    "fetch_k": 20,  # Candidatos antes del ranking MMR
                },
            )
        return self._retriever

    async def retrieve(self, query: str) -> tuple[str, list[dict]]:
        """
        Recupera los artículos más relevantes para una consulta.

        Returns:
            Tupla de (contexto_formateado, lista_de_fuentes)
        """
        retriever = self.get_retriever()
        docs: list[Document] = await retriever.ainvoke(query)

        if not docs:
            return "", []

        # Formatea el contexto con metadatos de fuente
        context_parts = []
        sources = []

        for i, doc in enumerate(docs, 1):
            metadata = doc.metadata
            ley = metadata.get("ley", "Ley no especificada")
            articulo = metadata.get("articulo", "")
            pagina = metadata.get("page", "")

            header = f"[Fuente {i}] {ley}"
            if articulo:
                header += f" — {articulo}"
            if pagina:
                header += f" (pág. {pagina})"

            context_parts.append(f"{header}\n{doc.page_content}")
            sources.append({
                "ley": ley,
                "articulo": articulo,
                "fragmento": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
            })

        context = "\n\n---\n\n".join(context_parts)
        return context, sources

    def ingest_documents(self, docs_path: str = "./legal_docs") -> int:
        """
        Ingesta documentos PDF del directorio indicado.
        Detecta automáticamente la ley por nombre de archivo.

        Convención de nombres:
          codigo_civil_jalisco.pdf
          codigo_civil_federal.pdf
          codigo_procedimientos_civiles_jalisco.pdf
          ley_registro_civil_jalisco.pdf
          etc.

        Returns:
            Número de chunks indexados.
        """
        docs_dir = Path(docs_path)
        if not docs_dir.exists():
            raise FileNotFoundError(f"Directorio de documentos no encontrado: {docs_path}")

        pdfs = list(docs_dir.glob("*.pdf"))
        if not pdfs:
            logger.warning(f"No se encontraron PDFs en {docs_path}")
            return 0

        logger.info(f"Encontrados {len(pdfs)} PDFs para indexar")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=[
                "\nArtículo",
                "\nARTÍCULO",
                "\nCapítulo",
                "\nCAPÍTULO",
                "\nTítulo",
                "\nTÍTULO",
                "\n\n",
                "\n",
                ". ",
            ],
        )

        all_chunks: list[Document] = []

        for pdf_path in pdfs:
            ley_nombre = _nombre_ley_desde_archivo(pdf_path.name)
            logger.info(f"Procesando: {pdf_path.name} → {ley_nombre}")

            try:
                loader = PyPDFLoader(str(pdf_path))
                pages = loader.load()

                # Añade metadatos de fuente a cada página
                for page in pages:
                    page.metadata["ley"] = ley_nombre
                    page.metadata["archivo"] = pdf_path.name

                chunks = splitter.split_documents(pages)

                # Extrae el número de artículo si está en el chunk
                for chunk in chunks:
                    chunk.metadata["articulo"] = _extraer_articulo(chunk.page_content)

                all_chunks.extend(chunks)
                logger.info(f"  → {len(chunks)} chunks generados")

            except Exception as e:
                logger.error(f"Error procesando {pdf_path.name}: {e}")
                continue

        if not all_chunks:
            return 0

        # Indexa en ChromaDB en lotes
        vs = self.get_vectorstore()
        batch_size = 100
        total = 0

        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            vs.add_documents(batch)
            total += len(batch)
            logger.info(f"Indexados {total}/{len(all_chunks)} chunks")

        logger.success(f"✅ Ingesta completada: {total} chunks en ChromaDB")
        return total

    def collection_stats(self) -> dict:
        """Retorna estadísticas de la colección."""
        try:
            vs = self.get_vectorstore()
            count = vs._collection.count()
            return {"total_chunks": count, "coleccion": settings.chroma_collection}
        except Exception as e:
            return {"error": str(e)}


def _nombre_ley_desde_archivo(filename: str) -> str:
    """Convierte el nombre de archivo en nombre legible de la ley."""
    mapping = {
        "codigo_civil_jalisco": "Código Civil del Estado de Jalisco",
        "codigo_civil_federal": "Código Civil Federal",
        "codigo_procedimientos_civiles_jalisco": "Código de Procedimientos Civiles del Estado de Jalisco",
        "ley_registro_civil_jalisco": "Ley del Registro Civil del Estado de Jalisco",
        "ley_familia_jalisco": "Código Familiar del Estado de Jalisco",
        "constitucion_jalisco": "Constitución Política del Estado de Jalisco",
        "constitucion_federal": "Constitución Política de los Estados Unidos Mexicanos",
        "ley_notariado_jalisco": "Ley del Notariado del Estado de Jalisco",
        "ley_arrendamiento_jalisco": "Ley de Arrendamiento Inmobiliario para el Estado de Jalisco",
    }
    base = filename.replace(".pdf", "").lower()
    for key, value in mapping.items():
        if key in base:
            return value
    # Si no está en el mapping, usa el nombre limpiado
    return base.replace("_", " ").title()


def _extraer_articulo(texto: str) -> str:
    """Intenta extraer el número de artículo del texto."""
    import re
    match = re.search(r"Art[íi]culo\s+(\d+(?:\s*[Bb]is)?)", texto, re.IGNORECASE)
    if match:
        return f"Artículo {match.group(1)}"
    return ""


# Singleton global
_rag_instance: Optional[LegalRAG] = None


def get_rag() -> LegalRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = LegalRAG()
    return _rag_instance
