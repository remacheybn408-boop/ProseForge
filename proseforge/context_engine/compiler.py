from __future__ import annotations

from dataclasses import dataclass

from .tokenizer import ConservativeTokenizer


@dataclass(frozen=True)
class CompiledContext:
    snapshot_id: str
    blocks: tuple[dict[str, object], ...]
    estimated_tokens: int
    source_ids: tuple[str, ...]
    excluded_ids: tuple[str, ...]
    compiler_version: str = "1"


def compile_context(snapshot_id: str, blocks: list[dict[str, object]], input_budget: int) -> CompiledContext:
    tokenizer = ConservativeTokenizer()
    ordered = sorted(blocks, key=lambda item: (not bool(item.get("pinned", False)), int(item.get("priority", 100))))
    selected: list[dict[str, object]] = []
    excluded: list[str] = []
    used = 0
    for block in ordered:
        tokens = tokenizer.count(str(block.get("content", "")))
        block_id = str(block.get("id", ""))
        if used + tokens <= input_budget or block.get("pinned", False):
            selected.append(block)
            used += tokens
        else:
            excluded.append(block_id)
    return CompiledContext(snapshot_id, tuple(selected), used, tuple(str(item.get("id", "")) for item in selected), tuple(excluded))
