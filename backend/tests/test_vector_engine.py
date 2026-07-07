from pathlib import Path

from app.utils.vector_engine import CodeVectorEngine


def test_vector_engine_indexes_and_returns_relevant_context(tmp_path: Path):
    source_dir = tmp_path / "src"
    source_dir.mkdir()

    sample_file = source_dir / "service.py"
    sample_file.write_text(
        "def fetch_user(user_id):\n"
        "    return {'id': user_id, 'active': True}\n",
        encoding="utf-8",
    )

    engine = CodeVectorEngine(source_dir)
    context = engine.search_context("user lookup")

    assert len(context) >= 1
    assert any("fetch_user" in chunk for chunk in context)
