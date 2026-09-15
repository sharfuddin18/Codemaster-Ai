from typing import Callable, Optional
from backend.app.utils.parser import LLMParser

class PatchHealer:
    """Agentic self-healing loop for applying patches with automatic error feedback and retry logic."""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def execute_with_healing(
        self, 
        initial_patch: str, 
        apply_func: Callable[[str], None], 
        llm_fix_func: Callable[[str, str], str]
    ) -> bool:
        """
        Attempts to apply a patch using apply_func. If it fails, catches the exception,
        sends the error back to the LLM via llm_fix_func, parses the new patch, and retries.
        """
        current_patch = initial_patch
        
        for attempt in range(1, self.max_retries + 1):
            try:
                apply_func(current_patch)
                return True  # Successfully applied!
            except Exception as e:
                error_msg = str(e)
                if attempt == self.max_retries:
                    raise RuntimeError(
                        f"Patch application failed permanently after {self.max_retries} attempts. "
                        f"Last error: {error_msg}"
                    )
                
                # Request corrected patch from LLM using error feedback
                raw_fix_response = llm_fix_func(current_patch, error_msg)
                current_patch = LLMParser.extract_patch(raw_fix_response)
                
        return False

