import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Iterable, List, Tuple

try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None


class VectorCacheService:
    """Persistent file-hash and embedding cache used by the vector index."""

    def __init__(self, db_path: str = ".codemaster/cache.db"):
        db_parent = Path(db_path).parent
        if str(db_parent) not in ("", "."):
            db_parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        if sqlite_vec is not None:
            try:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
            except Exception:
                pass
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS file_hashes (
                    file_path TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings_cache (
                    chunk_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    FOREIGN KEY (file_path) REFERENCES file_hashes (file_path) ON DELETE CASCADE
                )
                """
            )
            conn.commit()

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def get_file_hash(self, file_path: str) -> str | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT file_hash FROM file_hashes WHERE file_path = ?", (file_path,)).fetchone()
            return row[0] if row else None

    def is_file_unchanged(self, file_path: str, current_hash: str) -> bool:
        return self.get_file_hash(file_path) == current_hash

    def get_cached_embeddings(self, file_path: str) -> List[Tuple[str, List[float]]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT chunk_text, embedding_json FROM embeddings_cache WHERE file_path = ? ORDER BY chunk_id",
                (file_path,),
            ).fetchall()
            result = []
            for text, embedding_json in rows:
                try:
                    embedding = json.loads(embedding_json)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Corrupted embedding cache for {file_path}") from exc
                if not isinstance(embedding, list):
                    raise ValueError(f"Corrupted embedding cache for {file_path}")
                result.append((text, embedding))
            return result

    def save_file_embeddings(
        self, file_path: str, file_hash: str, chunks_with_embeddings: List[Tuple[str, List[float]]]
    ) -> None:
        with self._get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM embeddings_cache WHERE file_path = ?", (file_path,))
            conn.execute(
                """
                INSERT INTO file_hashes (file_path, file_hash)
                VALUES (?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (file_path, file_hash),
            )
            for idx, (text, embedding) in enumerate(chunks_with_embeddings):
                chunk_id = f"{file_path}::{idx}"
                conn.execute(
                    """
                    INSERT INTO embeddings_cache (chunk_id, file_path, chunk_text, embedding_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (chunk_id, file_path, text, json.dumps(embedding)),
                )
            conn.commit()

    def invalidate_file(self, file_path: str) -> None:
        """Remove all cached state for a file."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM file_hashes WHERE file_path = ?", (file_path,))
            conn.commit()

    def remove_missing_files(self, existing_files: Iterable[str]) -> int:
        """Delete cache entries whose files no longer exist in the indexed tree."""
        existing = {str(Path(path).resolve()) for path in existing_files}
        with self._get_connection() as conn:
            rows = conn.execute("SELECT file_path FROM file_hashes").fetchall()
            stale = [row[0] for row in rows if row[0] not in existing]
            for file_path in stale:
                conn.execute("DELETE FROM file_hashes WHERE file_path = ?", (file_path,))
            conn.commit()
        return len(stale)
