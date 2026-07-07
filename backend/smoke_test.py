import asyncio
import os
from pathlib import Path

from app.llm.factory import LLMFactory
from app.routes.health import health_check
from app.utils.vector_engine import CodeVectorEngine, IndexConfig


def main() -> None:
    os.environ.setdefault("PYTHONPATH", ".")
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ["OLLAMA_ENABLED"] = "False"

    provider = LLMFactory.create_provider("ollama")
    assert provider.__class__.__name__ == "OllamaProvider"

    result = asyncio.run(health_check())
    print("HEALTH_STATUS", result)

    repo_root = Path(__file__).resolve().parent
    engine = CodeVectorEngine(config=IndexConfig(source_dir=repo_root, exclude_paths=[".git", "__pycache__", ".venv", "node_modules"]))
    engine.build_index()
    results = engine.search_context("database initialization", top_k=3)
    print("TOP_RESULTS")
    for index, chunk in enumerate(results, start=1):
        print(f"{index}. {chunk[:600]}")


if __name__ == "__main__":
    main()
