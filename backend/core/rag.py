import asyncio
import logging
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from backend.config import settings
from backend.schemas.agent_schemas import FinalBrief

logger = logging.getLogger(__name__)


class RAGMemory:
    """ChromaDB-based memory for storing and retrieving prior briefs."""

    def __init__(self) -> None:
        self._embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._collection = self._client.get_or_create_collection(
            name="prism_briefs",
            embedding_function=self._embedding_fn,
        )

    def _chunk_brief(self, brief: FinalBrief) -> tuple:
        """Split a brief into chunks by section. Returns (documents, metadatas, ids)."""
        documents = []
        metadatas = []
        ids = []

        # Executive summary as first chunk
        documents.append(f"Executive Summary: {brief.executive_summary}")
        metadatas.append({
            "brief_id": brief.brief_id,
            "section_title": "Executive Summary",
            "query": brief.query,
            "created_at": brief.created_at,
        })
        ids.append(f"{brief.brief_id}_executive_summary")

        # Each section as a chunk
        for i, section in enumerate(brief.sections):
            documents.append(f"{section.title}: {section.content}")
            metadatas.append({
                "brief_id": brief.brief_id,
                "section_title": section.title,
                "query": brief.query,
                "created_at": brief.created_at,
            })
            ids.append(f"{brief.brief_id}_section_{i}")

        return documents, metadatas, ids

    async def store_brief(self, brief: FinalBrief) -> None:
        """Chunk and store a brief in ChromaDB."""
        documents, metadatas, ids = self._chunk_brief(brief)
        if not documents:
            return

        def _store() -> None:
            self._collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

        await asyncio.to_thread(_store)
        logger.info(f"Stored brief {brief.brief_id} ({len(documents)} chunks)")

    async def query_related(
        self, query: str, n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Find prior brief chunks related to a query."""
        def _query() -> Optional[dict]:
            count = self._collection.count()
            if count == 0:
                return None
            return self._collection.query(
                query_texts=[query],
                n_results=min(n_results, count),
            )

        results = await asyncio.to_thread(_query)
        if not results:
            return []

        related = []
        for i, doc in enumerate(results["documents"][0]):
            related.append({
                "content": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return related

    async def list_briefs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return summaries of stored briefs."""
        def _list() -> dict:
            return self._collection.get(
                where={"section_title": "Executive Summary"},
                limit=limit,
            )

        try:
            results = await asyncio.to_thread(_list)
        except Exception:
            # If collection is empty or filter fails, return empty
            return []

        briefs = []
        for i, doc in enumerate(results["documents"]):
            meta = results["metadatas"][i]
            briefs.append({
                "brief_id": meta["brief_id"],
                "query": meta["query"],
                "executive_summary": doc.replace("Executive Summary: ", "", 1),
                "created_at": meta["created_at"],
            })
        return briefs

    async def get_brief_chunks(self, brief_id: str) -> List[Dict[str, Any]]:
        """Retrieve all chunks for a specific brief."""
        def _get() -> dict:
            return self._collection.get(
                where={"brief_id": brief_id},
            )

        results = await asyncio.to_thread(_get)
        chunks = []
        for i, doc in enumerate(results["documents"]):
            chunks.append({
                "content": doc,
                "metadata": results["metadatas"][i],
            })
        return chunks


rag_memory = RAGMemory()
