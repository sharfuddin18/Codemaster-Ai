import subprocess

import pytest

from backend.app.services.hybrid_retriever import HybridRetriever
from backend.app.services.patch_generator import (
    PatchApplicationError,
    apply_unified_patch,
    format_patch_response,
    generate_unified_patch,
    validate_unified_patch,
)


class MockVectorEngine:
    def query(self, query: str, top_k: int = 5):
        return [
            {"id": "doc1", "score": 0.5},
            {"id": "doc2", "score": 0.5},
            {"id": "doc3", "score": 0.0},
        ]


def test_hybrid_retriever_sparse_and_dense():
    docs = [
        {"id": "doc1", "content": "def calculate_tax(amount): return amount * 0.2"},
        {"id": "doc2", "content": "class UserProfile: def __init__(self, name): self.name = name"},
        {"id": "doc3", "content": "def process_payment(): pass"},
    ]
    retriever = HybridRetriever(dense_vector_engine=MockVectorEngine())
    retriever.index_documents(docs)
    results = retriever.search("UserProfile", top_k=2, alpha=0.2)
    assert len(results) == 2
    assert results[0]["id"] == "doc2"
    assert results[0]["hybrid_score"] > 0


def test_generate_unified_patch():
    orig = "def hello():\n    print('Hello World')\n"
    mod = "def hello():\n    print('Hello Codemaster AI')\n"
    patch_res = generate_unified_patch("src/hello.py", orig, mod)
    assert patch_res["has_changes"] is True
    assert "--- a/src/hello.py" in patch_res["patch"]


def test_generate_patch_no_changes():
    orig = "def hello():\n    print('Hello World')\n"
    patch_res = generate_unified_patch("src/hello.py", orig, orig)
    assert patch_res["has_changes"] is False
    assert format_patch_response(patch_res) == "No changes detected for src/hello.py"


def test_patch_validation_and_application(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    target = repo / "hello.py"
    original = "print('hello')\n"
    modified = "print('hello codemaster')\n"
    target.write_text(original, encoding="utf-8")

    patch = generate_unified_patch("hello.py", original, modified)["patch"]
    validate_unified_patch(repo, patch)
    apply_unified_patch(repo, patch)
    assert target.read_text(encoding="utf-8") == modified


def test_patch_failures_are_explicit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    target = repo / "hello.py"
    target.write_text("print('current')\n", encoding="utf-8")

    bad_patch = "--- a/hello.py\n+++ b/hello.py\n@@ -1 +1 @@\n-print('missing')\n+print('changed')\n"
    with pytest.raises(PatchApplicationError):
        validate_unified_patch(repo, bad_patch)


def test_patch_path_traversal_is_rejected():
    with pytest.raises(ValueError):
        generate_unified_patch("../outside.py", "a\n", "b\n")
