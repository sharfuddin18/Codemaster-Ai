import os
from pathlib import Path

from app.utils.vector_engine import CodeVectorEngine


def main() -> None:
    os.environ.setdefault("PYTHONPATH", ".")
    repo_root = Path(__file__).resolve().parent
    engine = CodeVectorEngine(repo_root)
    engine.build_index()
    results = engine.search_context("database initialization", top_k=3)
    print("TOP_RESULTS")
    for index, chunk in enumerate(results, start=1):
        print(f"{index}. {chunk[:600]}")


if __name__ == "__main__":
    main()
