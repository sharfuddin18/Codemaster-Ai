import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import faiss
import numpy as np

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
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".java",
            ".go",
            ".rs",
            ".c",
            ".cpp",
            ".cs",
            ".php",
            ".rb",
            ".sh",
            ".sql",
            ".md",
            ".txt",
        }
    )


class CodeVectorEngine:
    """Simple local vector index over code files using sentence-transformers + FAISS."""

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
        self._state = self.INITIALIZING
        self.chunks = []
        self.index = None

        try:
            if source_dir is not None:
                self.source_dir = self._resolve_source_dir(source_dir)
                if self.config.source_dir is None:
                    self.config.source_dir = self.source_dir
            elif self.source_dir is None:
                self.source_dir = Path.cwd().resolve()

            if self.source_dir is None:
                self._loaded = True
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
                print(f"No source files found under {self.source_dir}")
                return

            print(f"Indexing {len(files)} files from {self.source_dir}")
            for file_path in files:
                print(f"Indexing: {file_path.relative_to(self.source_dir)}")
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
                self._state = self.READY
                print("Indexing complete! No chunks were created.")
                return

            embeddings = self._encode_texts(self.chunks)
            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatL2(dimension)
            self.index.add(embeddings.astype("float32"))
            self._loaded = True
            self._state = self.READY
            print(f"Indexing complete! Added {len(self.chunks)} chunks from {len(files)} files.")
        except Exception as exc:
            self._loaded = False
            self._state = self.FAILED
            logger.exception("Vector index build failed: %s", exc)
            raise

    def search_context(self, query: str, top_k: int = 3) -> List[str]:
        if self._state != self.READY:
            raise RuntimeError("CodeVectorEngine is not ready for search")
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
