import asyncio
from pathlib import Path

from app.llm.factory import LLMFactory
from app.routes.health import health_check
from app.utils.vector_engine import CodeVectorEngine, IndexConfig


def test_vector_engine_indexes_and_returns_relevant_context(tmp_path: Path):
    source_dir = tmp_path / "src"
    source_dir.mkdir()

    sample_file = source_dir / "service.py"
    sample_file.write_text(
        "def fetch_user(user_id):\n"
        "    return {'id': user_id, 'active': True}\n",
        encoding="utf-8",
    )

    engine = CodeVectorEngine(config=IndexConfig(source_dir=source_dir))
    context = engine.search_context("user lookup")

    assert len(context) >= 1
    assert any("fetch_user" in chunk for chunk in context)


def test_vector_engine_respects_exclusion_rules_and_raises_when_not_ready(tmp_path: Path):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    excluded_dir = tmp_path / ".git"
    excluded_dir.mkdir()

    included_file = source_dir / "service.py"
    included_file.write_text(
        "def fetch_user(user_id):\n"
        "    return {'id': user_id, 'active': True}\n",
        encoding="utf-8",
    )
    excluded_file = excluded_dir / "config"
    excluded_file.write_text("secret", encoding="utf-8")

    engine = CodeVectorEngine(config=IndexConfig(source_dir=tmp_path, exclude_paths=[".git", "node_modules"]))
    engine.build_index()
    context = engine.search_context("user lookup")

    assert len(context) >= 1
    assert any("fetch_user" in chunk for chunk in context)
    assert all("secret" not in chunk for chunk in context)

    engine._state = "FAILED"
    try:
        engine.search_context("user lookup")
    except RuntimeError as exc:
        assert "not ready" in str(exc).lower()
    else:
        raise AssertionError("search_context should raise once the engine is not ready")


def test_factory_returns_expected_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    provider = LLMFactory.create_provider()

    assert provider.__class__.__name__ == "OllamaProvider"


def test_health_check_returns_degraded_without_connection(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_ENABLED", "False")

    result = asyncio.run(health_check())

    assert result["status"] == "degraded"
    assert "provider" in result
