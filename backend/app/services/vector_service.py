import logging
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils.vector_engine import CodeVectorEngine

logger = logging.getLogger("codemaster-ai")


class VectorService:
    """Lightweight document-level vector API backed by the embedding utility."""

    def __init__(self, source_dir: Optional[str] = None, model_name: Optional[str] = None):
        self.engine = CodeVectorEngine(
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

        try:
            q_emb = self.engine._encode_texts([query])
        except Exception as exc:
            logger.exception("VectorService: failed to encode query: %s", exc)
            raise RuntimeError("Vector query encoding failed") from exc

        if self.embeddings is None or self.embeddings.shape[0] == 0:
            return [{"id": doc.get("id"), "score": 0.0} for doc in self.documents][:top_k]

        q_vec = q_emb[0].astype("float32")
        mat = self.embeddings.astype("float32")
        sims = (np.dot(mat, q_vec) + 1.0) / 2.0
        results = [
            {"id": self.ids[idx], "score": float(score)}
            for idx, score in enumerate(sims)
        ]
        results.sort(key=lambda item: (-item["score"], str(item["id"])))
        return results[:top_k]
