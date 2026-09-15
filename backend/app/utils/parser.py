import re
from typing import Optional

class LLMParser:
    """Defensive parser to strip conversational fluff from local LLMs and extract clean code or patches."""
    
    @staticmethod
    def extract_code_block(text: str, language: Optional[str] = None) -> str:
        """Extracts content from markdown code blocks (e.g., ```python ... ``` or ```diff ... ```)."""
        if not text:
            return ""
        
        # Build pattern based on optional language specification
        lang_str = language if language else r"\w*"
        pattern = rf"```{lang_str}\s*\n(.*?)\s*```"
        
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            # Return the first matching code block, stripped of leading/trailing whitespace
            return matches[0].strip()
            
        # Fallback: if no markdown block is found, return original text stripped
        return text.strip()

    @staticmethod
    def extract_patch(text: str) -> str:
        """Specifically extracts git diff or patch blocks from LLM responses."""
        # Try looking for diff block first
        diff_block = LLMParser.extract_code_block(text, "diff")
        if diff_block != text.strip():
            return diff_block
            
        # If no explicit diff block, try generic code block
        generic_block = LLMParser.extract_code_block(text)
        if "@@" in generic_block or "diff --git" in generic_block:
            return generic_block
            
        return text.strip()

