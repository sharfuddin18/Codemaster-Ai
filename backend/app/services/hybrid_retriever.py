import logging
import re
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi

logger = logging.getLogger("codemaster-ai")


class HybridRetriever:
    """Combines dense vector search with sparse BM25 keyword search."""

    def __init__(self, dense_vector_engine=None):
        self.dense_vector_engine = dense_vector_engine
        self.documents: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Okapi] = None

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9_]+", text.lower())

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Index unique documents while preserving their metadata."""
        unique: Dict[str, Dict[str, Any]] = {}
        for doc in documents or []:
            if not isinstance(doc, dict):
                continue
            doc_id = str(doc.get("id", ""))
            if not doc_id or doc_id in unique:
                continue
            unique[doc_id] = dict(doc)

        self.documents = list(unique.values())
        corpus = [self._tokenize(str(doc.get("content", ""))) for doc in self.documents]
        self.bm25 = BM25Okapi(corpus) if corpus else None

        if self.dense_vector_engine and hasattr(self.dense_vector_engine, "index_documents"):
            self.dense_vector_engine.index_documents(self.documents)

    @staticmethod
    def _normalize_scores(scores: List[float]) -> List[float]:
        if not scores:
            return []
        finite = [float(score) for score in scores]
        min_s, max_s = min(finite), max(finite)
        score_range = max_s - min_s
        if score_range <= 0:
            return [0.0 for _ in finite]
        return [(score - min_s) / score_range for score in finite]

    def search(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Return deterministic hybrid-ranked results with explicit scores."""
        if not isinstance(query, str) or not query.strip():
            return []
        if not self.documents:
            return []
        if not isinstance(top_k, int) or top_k < 1:
            return []
        if not 0.0 <= float(alpha) <= 1.0:
            raise ValueError("alpha must be between 0.0 and 1.0")
        if not 0.0 <= float(min_score) <= 1.0:
            raise ValueError("min_score must be between 0.0 and 1.0")

        raw_bm25_scores = [0.0] * len(self.documents)
        if self.bm25 is not None:
            raw_bm25_scores = list(self.bm25.get_scores(self._tokenize(query)))
        norm_bm25_scores = self._normalize_scores(raw_bm25_scores)

        dense_scores_map: Dict[str, float] = {}
        if self.dense_vector_engine is not None:
            dense_results = self.dense_vector_engine.query(query, top_k=len(self.documents))
            for result in dense_results or []:
                if isinstance(result, dict) and result.get("id") is not None:
                    dense_scores_map[str(result["id"])] = float(result.get("score", 0.0))

        raw_dense_scores = [dense_scores_map.get(str(doc.get("id")), 0.0) for doc in self.documents]
        norm_dense_scores = self._normalize_scores(raw_dense_scores)

        combined_results = []
        for index, doc in enumerate(self.documents):
            dense_score = norm_dense_scores[index]
            bm25_score = norm_bm25_scores[index]
            hybrid_score = (float(alpha) * dense_score) + ((1.0 - float(alpha)) * bm25_score)
            entry = dict(doc)
            entry["hybrid_score"] = hybrid_score
            entry["bm25_score"] = bm25_score
            entry["dense_score"] = dense_score
            combined_results.append(entry)

        if min_score > 0.0:
            combined_results = [result for result in combined_results if result["hybrid_score"] >= float(min_score)]

        combined_results.sort(key=lambda result: (-result["hybrid_score"], str(result.get("id", ""))))
        return combined_results[:top_k]
