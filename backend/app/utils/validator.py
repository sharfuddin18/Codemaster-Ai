import os
import re

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
            
        for path in target_paths:
            full_path = os.path.join(root_dir, path)
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                return False
                
        return True
