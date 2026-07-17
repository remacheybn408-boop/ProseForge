from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Memory:
    scope: str
    key: str
    value: str
    source_artifact_id: str
    active: bool = True

class ScopedMemory:
    def __init__(self): self._items: dict[tuple[str, str], Memory] = {}
    def put(self, item: Memory) -> None: self._items[(item.scope, item.key)] = item
    def get(self, scope: str, key: str) -> Memory | None: return self._items.get((scope, key))
    def active_for(self, scope: str) -> list[Memory]: return [item for (item_scope, _), item in self._items.items() if item_scope == scope and item.active]
