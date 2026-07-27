import hashlib
import sqlean as sqlite3
import json
import os
import sqlite_vec
from typing import List, Tuple, Optional

class VectorCacheService:
    def __init__(self, db_path: str = ".codemaster/cache.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_hashes (
                    file_path TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embeddings_cache (
                    chunk_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    FOREIGN KEY (file_path) REFERENCES file_hashes (file_path) ON DELETE CASCADE
                )
            """)
            conn.commit()

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()

    def is_file_unchanged(self, file_path: str, current_hash: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_hash FROM file_hashes WHERE file_path = ?", (file_path,))
            row = cursor.fetchone()
            return row is not None and row[0] == current_hash

    def get_cached_embeddings(self, file_path: str) -> List[Tuple[str, List[float]]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chunk_text, embedding_json FROM embeddings_cache WHERE file_path = ?",
                (file_path,)
            )
            rows = cursor.fetchall()
            return [(row[0], json.loads(row[1])) for row in rows]

    def save_file_embeddings(
        self, file_path: str, file_hash: str, chunks_with_embeddings: List[Tuple[str, List[float]]]
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO file_hashes (file_path, file_hash) VALUES (?, ?)",
                (file_path, file_hash)
            )
            cursor.execute("DELETE FROM embeddings_cache WHERE file_path = ?", (file_path,))
            
            for idx, (text, embedding) in enumerate(chunks_with_embeddings):
                chunk_id = f"{file_path}::{idx}"
                cursor.execute(
                    """
                    INSERT INTO embeddings_cache (chunk_id, file_path, chunk_text, embedding_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (chunk_id, file_path, text, json.dumps(embedding))
                )
            conn.commit()