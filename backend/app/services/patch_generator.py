import difflib
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("codemaster-ai")


class PatchApplicationError(RuntimeError):
    """Raised when a patch cannot be validated or applied."""


def generate_unified_patch(file_path: str, original_content: str, modified_content: str) -> Dict[str, Any]:
    """Generate a standard Git unified patch."""
    if not file_path or Path(file_path).is_absolute() or ".." in Path(file_path).parts:
        raise ValueError("file_path must be a relative repository path")

    orig_lines = original_content.splitlines(keepends=True)
    mod_lines = modified_content.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    patch_text = "".join(diff)
    return {
        "file_path": file_path,
        "patch": patch_text,
        "has_changes": bool(patch_text.strip()),
        "format": "git_unified_diff",
    }


def validate_unified_patch(repo_root: str | Path, patch_text: str) -> None:
    """Validate a patch without changing the working tree."""
    if not patch_text or not patch_text.strip():
        raise PatchApplicationError("Patch is empty")
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise PatchApplicationError(f"Repository root does not exist: {root}")
    try:
        result = subprocess.run(
            ["git", "apply", "--check", "--recount", "--whitespace=error"],
            input=patch_text,
            text=True,
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise PatchApplicationError(f"Unable to execute git apply: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PatchApplicationError(f"Patch validation failed: {detail or 'unknown git error'}")


def apply_unified_patch(repo_root: str | Path, patch_text: str) -> None:
    """Validate and apply a patch, surfacing failures instead of swallowing them."""
    validate_unified_patch(repo_root, patch_text)
    root = Path(repo_root).resolve()
    result = subprocess.run(
        ["git", "apply", "--recount", "--whitespace=error"],
        input=patch_text,
        text=True,
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PatchApplicationError(f"Patch application failed: {detail or 'unknown git error'}")


def format_patch_response(patch_res: Dict[str, Any]) -> str:
    """Format a patch dictionary into a response string."""
    if not patch_res.get("has_changes"):
        return f"No changes detected for {patch_res.get('file_path')}"
    return patch_res.get("patch", "")
