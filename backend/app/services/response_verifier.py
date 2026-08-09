import re
from typing import Tuple, List, Optional, Iterable


ABSTAIN_PHRASE = "I don't have enough repository context to answer this. Abstaining."


def _extract_citation_indices(text: str) -> List[int]:
    if not text:
        return []
    matches = re.findall(r"\[\s*(\d+)\s*\]", text)
    return [int(m) for m in matches]


def is_explicit_abstention(text: str) -> bool:
    if not text:
        return False
    return ABSTAIN_PHRASE in text


def verify_response(text: str, allowed_indices: Optional[Iterable[int]] = None) -> Tuple[bool, str, List[int]]:
    """Verify model output for provenance requirements.

    - If the model explicitly abstains using the known phrase, return ok.
    - Otherwise require at least one citation token [N].
    - If `allowed_indices` is provided, ensure all cited indices are within that set.

    Returns (ok, reason, cited_indices).
    """
    if is_explicit_abstention(text):
        return True, "explicit abstention", []

    cited = _extract_citation_indices(text)
    if not cited:
        return False, "missing citations", []

    if allowed_indices is not None:
        allowed_set = set(allowed_indices)
        invalid = [i for i in cited if i not in allowed_set]
        if invalid:
            return False, f"invalid citation indices: {invalid}", cited

    return True, "has citations", cited
