import os
import pytest
from backend.app.services.cache_service import VectorCacheService

def test_cache_service_file_hashing_and_persistence(tmp_path):
    db_file = tmp_path / "cache.db"
    cache_service = VectorCacheService(db_path=str(db_file))
    
    test_code_file = tmp_path / "test_script.py"
    test_code_file.write_text("def hello(): return 'world'")
    
    file_path = str(test_code_file)
    initial_hash = cache_service.compute_file_hash(file_path)
    
    # File should not be cached initially
    assert not cache_service.is_file_unchanged(file_path, initial_hash)
    
    mock_embeddings = [("def hello(): return 'world'", [0.1, 0.2, 0.3])]
    cache_service.save_file_embeddings(file_path, initial_hash, mock_embeddings)
    
    # File should now be recognized as unchanged
    assert cache_service.is_file_unchanged(file_path, initial_hash)
    
    cached_data = cache_service.get_cached_embeddings(file_path)
    assert len(cached_data) == 1
    assert cached_data[0][0] == "def hello(): return 'world'"
    assert cached_data[0][1] == [0.1, 0.2, 0.3]