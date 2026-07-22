import pytest
from backend.app.services.hybrid_retriever import HybridRetriever
from backend.app.services.patch_generator import (
    generate_unified_patch,
    format_patch_response,
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
        {
            "id": "doc2",
            "content": "class UserProfile: def __init__(self, name): self.name = name",
        },
        {"id": "doc3", "content": "def process_payment(): pass"},
    ]
    engine = MockVectorEngine()
    retriever = HybridRetriever(dense_vector_engine=engine)
    retriever.index_documents(docs)

    results = retriever.search("UserProfile", top_k=2, alpha=0.2)

    assert len(results) == 2
    assert results[0]["id"] == "doc2"
    assert results[0]["hybrid_score"] > 0

def test_generate_unified_patch():
    orig = "def hello():\n    print('Hello World')\n"
    mod = "def hello():\n    print('Hello Codemaster AI')\n"
    file_path = "src/hello.py"

    patch_res = generate_unified_patch(file_path, orig, mod)

    assert patch_res["has_changes"] is True
    assert "--- a/src/hello.py" in patch_res["patch"]

def test_generate_patch_no_changes():
    orig = "def hello():\n    print('Hello World')\n"
    file_path = "src/hello.py"

    patch_res = generate_unified_patch(file_path, orig, orig)

    assert patch_res["has_changes"] is False
    assert (
        format_patch_response(patch_res)
        == f"No changes detected for {file_path}"
    )
