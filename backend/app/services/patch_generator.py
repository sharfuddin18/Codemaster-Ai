import difflib
import logging
from typing import Dict, Any

logger = logging.getLogger("codemaster-ai")


def generate_unified_patch(
    file_path: str, original_content: str, modified_content: str
) -> Dict[str, Any]:
    """Generates a standard Git unified patch (.patch format)."""
    orig_lines = original_content.splitlines(keepends=True)
    mod_lines = modified_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )

    patch_text = "".join(diff)
    has_changes = bool(patch_text.strip())

    return {
        "file_path": file_path,
        "patch": patch_text,
        "has_changes": has_changes,
        "format": "git_unified_diff"
    }


def format_patch_response(patch_res: Dict[str, Any]) -> str:
    """Formats patch dictionary into response string."""
    if not patch_res.get("has_changes"):
        return f"No changes detected for {patch_res.get('file_path')}"
    return patch_res.get("patch", "")