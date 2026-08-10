import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import faiss
import numpy as np

from ..services.cache_service import VectorCacheService

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - dependency may be unavailable in some environments
    SentenceTransformer = None

logger = logging.getLogger("codemaster-ai")


@dataclass
class IndexConfig:
    """Configuration describing how the repository index should be built."""

    source_dir: Optional[str | Path] = None
    exclude_paths: List[str] = field(default_factory=lambda: [".git", "__pycache__", ".venv", "node_modules"])
    supported_extensions: set[str] = field(
        default_factory=lambda: {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp",
            ".cs", ".php", ".rb", ".sh", ".sql", ".md", ".txt",
        }
    )
    cache_db_path: Optional[str | Path] = None
    persist_path: Optional[str | Path] = None


class CodeVectorEngine:
    """Local vector index over code files using sentence-transformers + FAISS."""

    INITIALIZING = "INITIALIZING"
    READY = "READY"
    FAILED = "FAILED"

    def __init__(
        self,
        source_dir: Optional[str | Path] = None,
        config: Optional[IndexConfig] = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.config = config or IndexConfig(source_dir=source_dir)
        if source_dir is not None and self.config.source_dir is None:
            self.config.source_dir = source_dir

        self.source_dir = self._resolve_source_dir(self.config.source_dir or source_dir)
        self.model_name = model_name
        self.model = None
        self.index = None
        self.chunks: List[str] = []
        self._loaded = False
        self._state = self.INITIALIZING
        self._embedding_dimension: Optional[int] = None
        self.cache = (
            VectorCacheService(str(self.config.cache_db_path))
            if self.config.cache_db_path is not None
            else None
        )

        if self.source_dir is not None:
            self.build_index(self.source_dir)

    def _resolve_source_dir(self, source_dir: Optional[str | Path]) -> Optional[Path]:
        if source_dir is None:
            return Path.cwd().resolve()
        return Path(source_dir).resolve()

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
        if not texts:
            return np.empty((0, self._embedding_dimension or 128), dtype="float32")
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
                digest = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).digest()
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
        excluded = set((self.config.exclude_paths or []) + [".git", "__pycache__", ".venv", "node_modules"])
        for path in sorted(self.source_dir.rglob("*")):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(self.source_dir).parts
            if any(part in excluded for part in rel_parts):
                continue
            if path.suffix.lower() in self.config.supported_extensions:
                files.append(path)
        return files

    def _chunk_text(self, text: str, size: int = 120, overlap: int = 40) -> List[str]:
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

    def _build_file_chunks(self, file_path: Path) -> tuple[List[str], np.ndarray]:
        text = file_path.read_text(encoding="utf-8")
        raw_chunks = self._chunk_text(text)
        contexts = [f"File: {file_path.relative_to(self.source_dir)}\n{chunk}" for chunk in raw_chunks]
        if not contexts:
            return [], np.empty((0, self._embedding_dimension or 128), dtype="float32")

        if self.cache is not None:
            file_path_str = str(file_path)
            file_hash = self.cache.compute_file_hash(file_path_str)
            if self.cache.is_file_unchanged(file_path_str, file_hash):
                cached = self.cache.get_cached_embeddings(file_path_str)
                cached_by_text = {text: embedding for text, embedding in cached}
                if all(context in cached_by_text for context in contexts):
                    embeddings = np.asarray([cached_by_text[context] for context in contexts], dtype="float32")
                    if embeddings.ndim == 2 and embeddings.shape[0] == len(contexts):
                        self._embedding_dimension = embeddings.shape[1]
                        return contexts, embeddings

            embeddings = self._encode_texts(contexts)
            self.cache.save_file_embeddings(
                file_path_str,
                file_hash,
                [(context, embedding.tolist()) for context, embedding in zip(contexts, embeddings)],
            )
            if embeddings.size:
                self._embedding_dimension = embeddings.shape[1]
            return contexts, embeddings

        embeddings = self._encode_texts(contexts)
        if embeddings.size:
            self._embedding_dimension = embeddings.shape[1]
        return contexts, embeddings

    def build_index(self, source_dir: Optional[str | Path] = None) -> None:
        self._state = self.INITIALIZING
        self.chunks = []
        self.index = None
        self._embedding_dimension = None

        try:
            if source_dir is not None:
                self.source_dir = self._resolve_source_dir(source_dir)
                if self.config.source_dir is None:
                    self.config.source_dir = self.source_dir
            elif self.source_dir is None:
                self.source_dir = Path.cwd().resolve()

            if self.source_dir is None:
                self._loaded = False
                self._state = self.FAILED
                return
            if not self.source_dir.exists():
                self._loaded = False
                self._state = self.FAILED
                raise FileNotFoundError(f"Index source directory does not exist: {self.source_dir}")

            files = self._iter_source_files()
            if not files:
                self._loaded = True
                self._state = self.READY
                return

            embedding_blocks: List[np.ndarray] = []
            for file_path in files:
                try:
                    contexts, embeddings = self._build_file_chunks(file_path)
                except Exception as exc:
                    logger.warning("Skipping %s due to read/index error: %s", file_path, exc)
                    continue
                self.chunks.extend(contexts)
                if embeddings.size:
                    embedding_blocks.append(embeddings)

            if not self.chunks or not embedding_blocks:
                self._loaded = True
                self._state = self.READY
                return

            embeddings = np.vstack(embedding_blocks).astype("float32")
            self._embedding_dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatL2(self._embedding_dimension)
            self.index.add(embeddings)
            self._loaded = True
            self._state = self.READY
        except Exception as exc:
            self._loaded = False
            self._state = self.FAILED
            logger.exception("Vector index build failed: %s", exc)
            raise

    def persist(self, path: Optional[str | Path] = None) -> Path:
        """Persist the FAISS index and chunk metadata for later reload."""
        if self._state != self.READY or self.index is None:
            raise RuntimeError("CodeVectorEngine is not ready for persistence")
        target = Path(path or self.config.persist_path or ".codemaster/vector_index")
        target.parent.mkdir(parents=True, exist_ok=True)
        index_path = target.with_suffix(".faiss")
        metadata_path = target.with_suffix(".json")
        faiss.write_index(self.index, str(index_path))
        metadata_path.write_text(
            json.dumps({"model_name": self.model_name, "chunks": self.chunks}, ensure_ascii=False),
            encoding="utf-8",
        )
        return index_path

    def load(self, path: Optional[str | Path] = None) -> None:
        """Reload a previously persisted FAISS index and metadata."""
        target = Path(path or self.config.persist_path or ".codemaster/vector_index")
        index_path = target.with_suffix(".faiss")
        metadata_path = target.with_suffix(".json")
        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(f"Persisted vector index is incomplete: {target}")
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            chunks = metadata.get("chunks")
            if not isinstance(chunks, list) or not all(isinstance(chunk, str) for chunk in chunks):
                raise ValueError("Persisted vector metadata is invalid")
            index = faiss.read_index(str(index_path))
            if index.ntotal != len(chunks):
                raise ValueError("Persisted vector index and metadata have different sizes")
            self.index = index
            self.chunks = chunks
            self._embedding_dimension = index.d
            self._loaded = True
            self._state = self.READY
        except Exception:
            self._loaded = False
            self._state = self.FAILED
            raise

    def search_context(self, query: str, top_k: int = 3) -> List[str]:
        if self._state != self.READY:
            raise RuntimeError("CodeVectorEngine is not ready for search")
        if not isinstance(query, str) or not query.strip():
            return []
        if not self._loaded or not self.chunks or self.index is None:
            return []
        if not isinstance(top_k, int) or top_k < 1:
            return []

        query_embedding = self._encode_texts([query])[0:1]
        _, indices = self.index.search(query_embedding.astype("float32"), min(top_k, len(self.chunks)))
        return [self.chunks[int(idx)] for idx in indices[0] if idx >= 0]
