import re
from pathlib import Path

class PathValidator:
    """Validates that file paths referenced in patches exist within the local workspace to prevent context hallucination."""
    
    @staticmethod
    def extract_target_paths_from_patch(patch_text: str) -> list[str]:
        """Extracts target file paths from git diff headers (e.g., +++ b/backend/app/main.py)."""
        paths = []
        # Process line by line to safely handle leading indentation in multiline test strings
        for line in patch_text.splitlines():
            clean_line = line.strip()
            match = re.match(r"^(?:\+\+\+|---)\s+[ab]/(.+)$", clean_line)
            if match:
                path = match.group(1).strip()
                if path and path != "/dev/null":
                    paths.append(path)
        return list(set(paths))  # Unique paths

    @staticmethod
    def validate_patch_provenance(patch_text: str, root_dir: str = ".") -> bool:
        """Checks if all files targeted by the patch exist locally within the workspace root."""
        target_paths = PathValidator.extract_target_paths_from_patch(patch_text)
        
        if not target_paths:
            return False  # No valid paths found in patch headers
            
        root = Path(root_dir).resolve()
        for path in target_paths:
            full_path = (root / path).resolve()
            try:
                full_path.relative_to(root)
            except ValueError:
                return False
            if not full_path.is_file():
                return False
                
        return True
