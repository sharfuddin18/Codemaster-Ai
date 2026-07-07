import hashlib
import logging
import re
from pathlib import Path
from typing import List, Optional

import faiss
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - dependency may be unavailable in some environments
    SentenceTransformer = None

logger = logging.getLogger("codemaster-ai")


class CodeVectorEngine:
    """Simple local vector index over code files using sentence-transformers + FAISS."""

    def __init__(self, source_dir: Optional[str | Path] = None, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.source_dir = Path(source_dir) if source_dir else None
        self.model_name = model_name
        self.model = None
        self.index = None
        self.chunks: List[str] = []
        self._loaded = False

        if self.source_dir is not None:
            self.build_index(self.source_dir)

    def _ensure_model(self) -> None:
        if self.model is None:
            if SentenceTransformer is not None:
                try:
                    self.model = SentenceTransformer(self.model_name)
                    return
                except Exception as exc:
                    logger.warning("Falling back to keyword embeddings because sentence-transformers failed: %s", exc)
            self.model = "fallback"

    def _encode_texts(self, texts: List[str]) -> np.ndarray:
        self._ensure_model()
        if self.model == "fallback":
            return self._fallback_embeddings(texts)

        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return np.asarray(embeddings, dtype="float32")
        except Exception as exc:
            logger.warning("Embedding generation failed; using fallback embeddings: %s", exc)
            return self._fallback_embeddings(texts)

    def _fallback_embeddings(self, texts: List[str]) -> np.ndarray:
        dim = 128
        embeddings = []
        for text in texts:
            tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
            vector = np.zeros(dim, dtype="float32")
            for token in tokens:
                digest = hashlib.md5(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:2], "big") % dim
                vector[index] += 1.0
            if np.linalg.norm(vector) > 0:
                vector = vector / np.linalg.norm(vector)
            embeddings.append(vector)
        return np.vstack(embeddings)

    def _iter_source_files(self) -> List[Path]:
        if self.source_dir is None:
            return []

        files: List[Path] = []
        for path in sorted(self.source_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".cs", ".php", ".rb", ".sh", ".sql", ".md", ".txt"}:
                files.append(path)
        return files

    def _chunk_text(self, text: str, size: int = 400, overlap: int = 80) -> List[str]:
        if not text.strip():
            return []

        raw_lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        if not raw_lines:
            return []

        chunks: List[str] = []
        start = 0
        while start < len(raw_lines):
            end = min(start + size, len(raw_lines))
            piece = "\n".join(raw_lines[start:end])
            if piece:
                chunks.append(piece)
            if end >= len(raw_lines):
                break
            start += max(1, size - overlap)
        return chunks

    def build_index(self, source_dir: Optional[str | Path] = None) -> None:
        if source_dir is not None:
            self.source_dir = Path(source_dir)

        self.chunks = []
        self.index = None

        if self.source_dir is None:
            self._loaded = True
            return

        files = self._iter_source_files()
        if not files:
            self._loaded = True
            return

        for file_path in files:
            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("Skipping %s due to read error: %s", file_path, exc)
                continue

            for chunk in self._chunk_text(text):
                context = f"File: {file_path.relative_to(self.source_dir)}\n{chunk}"
                self.chunks.append(context)

        if not self.chunks:
            self._loaded = True
            return

        embeddings = self._encode_texts(self.chunks)
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings.astype("float32"))
        self._loaded = True

    def search_context(self, query: str, top_k: int = 3) -> List[str]:
        if not self._loaded or not self.chunks or self.index is None:
            return []

        query_embedding = self._encode_texts([query])[0:1]
        _, indices = self.index.search(query_embedding.astype("float32"), min(top_k, len(self.chunks)))

        results: List[str] = []
        for idx in indices[0]:
            if idx < 0:
                continue
            results.append(self.chunks[int(idx)])
        return results
