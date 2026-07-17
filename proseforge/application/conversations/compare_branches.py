from __future__ import annotations

from collections.abc import Sequence


def compare_messages(left: Sequence[object], right: Sequence[object]) -> dict[str, object]:
    """Return a stable comparison without mutating either branch history."""
    common = 0
    while common < min(len(left), len(right)) and getattr(left[common], "id", None) == getattr(right[common], "id", None):
        common += 1
    return {"common_count": common, "left": list(left[common:]), "right": list(right[common:])}
