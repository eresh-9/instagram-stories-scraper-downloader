thonfrom __future__ import annotations

from typing import Any, Dict, Iterable, Optional

def choose_best_version(versions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Choose the "best" media version from a list. We interpret "best" as the
    largest resolution (width * height). If that information is not available,
    we simply return the first entry.
    """
    best: Optional[Dict[str, Any]] = None
    best_score: int = -1

    for v in versions:
        if not isinstance(v, dict):
            continue
        width = v.get("width")
        height = v.get("height")

        if isinstance(width, int) and isinstance(height, int):
            score = width * height
        else:
            score = 0

        if best is None or score > best_score:
            best = v
            best_score = score

    return best or {}