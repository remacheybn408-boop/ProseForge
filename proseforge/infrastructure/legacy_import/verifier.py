from __future__ import annotations

from dataclasses import dataclass

from .sqlite_reader import LegacySnapshot


@dataclass(frozen=True)
class Verification:
    hash_mismatches: tuple[str, ...] = ()


def verify_snapshot(expected: LegacySnapshot, actual: LegacySnapshot) -> Verification:
    mismatches = []
    if len(expected.chapters) != len(actual.chapters):
        mismatches.append("chapter_count")
    for left, right in zip(expected.chapters, actual.chapters):
        if left.latest_hash != right.latest_hash:
            mismatches.append(f"chapter:{left.chapter_no}:latest_hash")
    if expected.outline_count != actual.outline_count:
        mismatches.append("outline_count")
    return Verification(tuple(mismatches))
