from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.llm.factory import LLMFactory
from backend.app.main import app
from backend.app.services import mcp_service  # type: ignore
from backend.app.services.cache_service import VectorCacheService
from backend.app.services.hybrid_retriever import HybridRetriever
from backend.app.utils import vector_engine
from backend.app.utils.vector_engine import CodeVectorEngine, IndexConfig


def test_hybrid_retrieval_handles_empty_queries_and_top_k():
    retriever = HybridRetriever()
    retriever.index_documents([{"id": "a", "content": "fetch_user"}])
    assert retriever.search("", top_k=5) == []
    assert retriever.search("fetch_user", top_k=0) == []
    assert retriever.search("fetch_user", top_k=1)[0]["id"] == "a"


def test_hybrid_retrieval_deduplicates_ids_and_validates_parameters():
    retriever = HybridRetriever()
    retriever.index_documents([
        {"id": "a", "content": "alpha identifier"},
        {"id": "a", "content": "duplicate identifier"},
        {"id": "b", "content": "beta identifier"},
    ])
    assert [doc["id"] for doc in retriever.search("alpha", top_k=5)] == ["a", "b"]
    with pytest.raises(ValueError):
        retriever.search("alpha", alpha=1.1)
    with pytest.raises(ValueError):
        retriever.search("alpha", min_score=1.1)


def test_vector_engine_persist_reload_and_invalid_state(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(vector_engine, "SentenceTransformer", None)
    source = tmp_path / "src"
    source.mkdir()
    (source / "service.py").write_text("def fetch_user(user_id):\n    return user_id\n", encoding="utf-8")
    empty_source = tmp_path / "empty"
    empty_source.mkdir()
    cache_db = tmp_path / "cache.db"
    persist = tmp_path / "vector_index"

    engine = CodeVectorEngine(config=IndexConfig(source_dir=source, cache_db_path=cache_db, persist_path=persist))
    assert engine.search_context("fetch_user", top_k=1)
    engine.persist()

    reloaded = CodeVectorEngine(source_dir=empty_source, config=IndexConfig(source_dir=empty_source))
    reloaded.load(persist)
    assert reloaded.chunks == engine.chunks
    assert reloaded.search_context("fetch_user", top_k=1)

    persist.with_suffix(".json").write_text('{"chunks": []}', encoding="utf-8")
    with pytest.raises(ValueError):
        reloaded.load(persist)
    assert reloaded._state == CodeVectorEngine.FAILED


def test_incremental_cache_reuses_unchanged_file_and_invalidates_deleted_file(tmp_path: Path):
    cache = VectorCacheService(str(tmp_path / "cache.db"))
    file_path = tmp_path / "sample.py"
    file_path.write_text("value = 1\n", encoding="utf-8")
    file_key = str(file_path.resolve())
    file_hash = cache.compute_file_hash(file_key)
    cache.save_file_embeddings(file_key, file_hash, [("value = 1", [0.1, 0.2])])

    assert cache.is_file_unchanged(file_key, file_hash)
    file_path.write_text("value = 2\n", encoding="utf-8")
    assert not cache.is_file_unchanged(file_key, cache.compute_file_hash(file_key))
    file_path.unlink()
    assert cache.remove_missing_files([]) == 1
    assert cache.get_file_hash(file_key) is None


def test_provider_factory_and_disabled_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_ENABLED", "false")
    provider = LLMFactory.create_provider()
    assert provider.provider_name == "ollama"
    assert provider.is_ready() is False

    monkeypatch.setenv("LLM_PROVIDER", "unknown-provider")
    fallback = LLMFactory.create_provider()
    assert fallback.provider_name == "fallback"


def test_mcp_runtime_retrieve_and_validation(monkeypatch):
    class FakeRetriever:
        def search(self, query, top_k=5, alpha=0.5, min_score=0.0):
            return [{
                "id": "1",
                "content": "File: src/service.py\ndef fetch_user(): pass",
                "hybrid_score": 0.9,
                "bm25_score": 1.0,
                "dense_score": 0.8,
            }][:top_k]

    monkeypatch.setattr("backend.app.routes.mcp.get_hybrid_retriever", lambda: FakeRetriever())
    app.state.activated = True
    with TestClient(app) as client:
        response = client.post("/mcp/retrieve", json={"query": "fetch_user", "top_k": 1})
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] == 1
        assert payload["results"][0]["file"] == "src/service.py"

        invalid = client.post("/mcp/retrieve", json={"query": "", "top_k": 1})
        assert invalid.status_code == 422
