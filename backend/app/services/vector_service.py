import logging
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils.vector_engine import CodeVectorEngine

logger = logging.getLogger("codemaster-ai")


class VectorService:
    """Lightweight document-level vector API backed by the embedding utility."""

    def __init__(
        self,
        source_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        engine: Optional[CodeVectorEngine] = None,
    ):
        self.engine = engine or CodeVectorEngine(
            source_dir=source_dir,
            model_name=model_name or "sentence-transformers/all-MiniLM-L6-v2",
            build_on_init=False,
        )
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        self.ids: List[str] = []

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Accept documents as {'id': str, 'content': str} and build embeddings."""
        self.documents = [doc for doc in (documents or []) if isinstance(doc, dict)]
        self.ids = [str(doc.get("id")) for doc in self.documents]
        texts = [str(doc.get("content", "")) for doc in self.documents]
        try:
            if self.documents:
                if (
                    texts == self.engine.chunks
                    and self.engine.index is not None
                    and self.engine.index.ntotal == len(texts)
                ):
                    self.embeddings = np.asarray(
                        self.engine.index.reconstruct_n(0, self.engine.index.ntotal),
                        dtype="float32",
                    )
                else:
                    self.embeddings = self.engine._encode_texts(texts)
            else:
                self.embeddings = None
        except Exception as exc:
            logger.exception("VectorService: failed to index documents: %s", exc)
            self.embeddings = None
            raise RuntimeError("Vector document indexing failed") from exc

    def query(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return top_k documents with similarity scores in [0,1]."""
        if not isinstance(query, str) or not query.strip() or not isinstance(top_k, int) or top_k < 1:
            return []
        if not self.documents:
            return []

        fallback = [{"id": doc.get("id"), "score": 0.0} for doc in self.documents][:top_k]

        try:
            q_emb = np.asarray(self.engine._encode_texts([query]), dtype="float32")
        except Exception as exc:
            logger.exception("VectorService: failed to encode query: %s", exc)
            return fallback

        try:
            mat = np.asarray(self.embeddings, dtype="float32")
        except Exception:
            return fallback

        if q_emb.size == 0 or mat.size == 0:
            return fallback

        if q_emb.ndim == 1:
            q_emb = q_emb.reshape(1, -1)
        if mat.ndim == 1:
            mat = mat.reshape(1, -1)

        if mat.shape[0] == 0 or q_emb.shape[1] != mat.shape[1]:
            return fallback

        sims = np.dot(mat, q_emb[0])
        if np.isscalar(sims):
            sims = np.asarray([float(sims)], dtype="float32")
        sims = np.asarray(sims, dtype="float32").reshape(-1)
        sims = np.clip((sims + 1.0) / 2.0, 0.0, 1.0)

        results = [
            {"id": self.ids[idx], "score": float(score)}
            for idx, score in enumerate(sims)
        ]
        results.sort(key=lambda item: (-item["score"], str(item["id"])))
        return results[:top_k]

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Compatibility alias used by the code-agent retrieval boundary."""
        return self.query(query, top_k=top_k)
