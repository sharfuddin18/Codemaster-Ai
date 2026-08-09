import logging
from typing import List, Dict, Any, Optional

from app.utils.vector_engine import CodeVectorEngine
import numpy as np

logger = logging.getLogger("codemaster-ai")


class VectorService:
    """Lightweight wrapper providing a simple document-level vector API.

    Exposes `index_documents(documents)` and `query(query, top_k)` which
    return a list of dicts like {"id": id, "score": float} where score is in [0,1].
    """

    def __init__(self, source_dir: Optional[str] = None, model_name: Optional[str] = None):
        # Use the CodeVectorEngine solely for its embedding utilities.
        self.engine = CodeVectorEngine(source_dir=None, config=None, model_name=(model_name or "sentence-transformers/all-MiniLM-L6-v2"))
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        self.ids: List[str] = []

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Accepts `documents` as list of {'id': str, 'content': str} and builds embeddings."""
        self.documents = documents or []
        self.ids = [doc.get("id") for doc in self.documents]
        texts = [doc.get("content", "") for doc in self.documents]
        try:
            # engine._encode_texts returns normalized embeddings when available
            self.engine._ensure_model()
            if self.documents:
                self.embeddings = self.engine._encode_texts(texts)
            else:
                self.embeddings = None
        except Exception as exc:
            logger.exception("VectorService: failed to index documents: %s", exc)
            self.embeddings = None

    def query(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return top_k documents with similarity scores in [0,1]."""
        if not self.documents:
            return []

        try:
            q_emb = self.engine._encode_texts([query])
        except Exception as exc:
            logger.exception("VectorService: failed to encode query: %s", exc)
            return []

        if self.embeddings is None or self.embeddings.shape[0] == 0:
            return [{"id": doc.get("id"), "score": 0.0} for doc in self.documents][:top_k]

        # embeddings are expected to be normalized; use dot product as cosine similarity
        q_vec = q_emb[0].astype("float32")
        mat = self.embeddings.astype("float32")
        sims = np.dot(mat, q_vec)

        # Convert cosine [-1,1] -> [0,1]
        sims = (sims + 1.0) / 2.0

        results = []
        for idx, score in enumerate(sims):
            results.append({"id": self.ids[idx], "score": float(score)})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
