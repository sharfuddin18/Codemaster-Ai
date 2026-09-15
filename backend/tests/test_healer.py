import pytest
from backend.app.utils.healer import PatchHealer

def test_patch_healer_succeeds_on_retry():
    attempts = 0
    
    def mock_apply_func(patch: str):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Line mismatch at line 42")
        # Succeeds on 3rd attempt
        pass

    def mock_llm_fix_func(failed_patch: str, error_msg: str) -> str:
        return f"```diff\n# Fixed patch after error: {error_msg}\n--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,1 @@\n-old\n+new\n```"

    healer = PatchHealer(max_retries=3)
    success = healer.execute_with_healing("initial_bad_patch", mock_apply_func, mock_llm_fix_func)
    
    assert success is True
    assert attempts == 3

def test_patch_healer_exhausts_retries():
    def mock_apply_func(patch: str):
        raise ValueError("Permanent syntax error")

    def mock_llm_fix_func(failed_patch: str, error_msg: str) -> str:
        return "Still broken patch"

    healer = PatchHealer(max_retries=2)
    
    with pytest.raises(RuntimeError) as exc_info:
        healer.execute_with_healing("bad_patch", mock_apply_func, mock_llm_fix_func)
        
    assert "after 2 attempts" in str(exc_info.value)

