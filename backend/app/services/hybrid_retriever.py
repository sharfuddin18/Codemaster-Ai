import logging
import re
from typing import Dict, List, Any, Optional
from rank_bm25 import BM25Okapi

logger = logging.getLogger("codemaster-ai")


class HybridRetriever:
    """Combines Dense Vector Search with Sparse BM25 Keyword Search."""

    def __init__(self, dense_vector_engine=None):
        self.dense_vector_engine = dense_vector_engine
        self.documents: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Okapi] = None

    def _tokenize(self, text: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
        return tokens

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        self.documents = documents
        corpus = [self._tokenize(doc.get("content", "")) for doc in documents]
        if corpus:
            self.bm25 = BM25Okapi(corpus)
        if self.dense_vector_engine and hasattr(self.dense_vector_engine, "index_documents"):
            self.dense_vector_engine.index_documents(documents)

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        if not scores:
            return []
        max_s = max(scores)
        min_s = min(scores)
        score_range = max_s - min_s
        if score_range > 0:
            return [(s - min_s) / score_range for s in scores]
        # When all dense scores are identical (e.g. 0.5 for all documents),
        # return 0.0 so that sparse/BM25 scores exclusively drive the relative ranking.
        return [0.0 for _ in scores]

    def search(
        self, query: str, top_k: int = 5, alpha: float = 0.5
    ) -> List[Dict[str, Any]]:
        if not self.documents:
            return []

        # 1. Compute Sparse (BM25) Scores & Normalize
        raw_bm25_scores = [0.0] * len(self.documents)
        if self.bm25:
            tokenized_query = self._tokenize(query)
            raw_bm25_scores = list(self.bm25.get_scores(tokenized_query))
        norm_bm25_scores = self._normalize_scores(raw_bm25_scores)

        # 2. Compute Dense Vector Scores & Normalize
        dense_scores_map: Dict[str, float] = {}
        if self.dense_vector_engine:
            dense_results = self.dense_vector_engine.query(
                query, top_k=len(self.documents)
            )
            for res in dense_results:
                dense_scores_map[res["id"]] = res.get("score", 0.0)

        raw_dense_scores = [dense_scores_map.get(doc.get("id"), 0.0) for doc in self.documents]
        norm_dense_scores = self._normalize_scores(raw_dense_scores)

        # 3. Combine Normalized Scores
        combined_results = []
        for i, doc in enumerate(self.documents):
            dense_score = norm_dense_scores[i]
            bm25_score = norm_bm25_scores[i]

            hybrid_score = (alpha * dense_score) + ((1 - alpha) * bm25_score)

            doc_entry = doc.copy()
            doc_entry["hybrid_score"] = hybrid_score
            doc_entry["bm25_score"] = bm25_score
            doc_entry["dense_score"] = dense_score
            combined_results.append(doc_entry)

        # 4. Sort and Return Top K
        combined_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return combined_results[:top_k]
