#!/usr/bin/env python3
"""
registry.py — 工作区注册表管理 v0.6.5

管理 workspace/registry.json:
- active_slot: 当前活跃的 DB slot ID
- slots array: 所有已注册的 slot 信息
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


class Registry:
    """Manages the workspace/registry.json file."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.workspace_dir = self.project_root / "workspace"
        self.registry_file = self.workspace_dir / "registry.json"

    def exists(self) -> bool:
        """Check if workspace is initialized."""
        return self.registry_file.exists()

    def load(self) -> Dict:
        """Load registry or return empty dict."""
        if not self.registry_file.exists():
            return {"active_slot": "", "slots": []}
        return json.loads(self.registry_file.read_text(encoding="utf-8"))

    def save(self, data: Dict) -> None:
        """Save registry data."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self.registry_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_active_slot(self) -> str:
        """Get the currently active slot ID."""
        data = self.load()
        return data.get("active_slot", "")

    def get_active_db_path(self) -> Optional[Path]:
        """Get the novel.db path for the currently active slot."""
        active = self.get_active_slot()
        if not active:
            return None
        return self.workspace_dir / active / "novel.db"

    def set_active_slot(self, slot_id: str) -> None:
        """Set the active slot ID."""
        data = self.load()
        data["active_slot"] = slot_id
        self.save(data)

    def list_slots(self) -> List[Dict]:
        """Get all registered slots."""
        data = self.load()
        return data.get("slots", [])

    def get_slot(self, slot_id: str) -> Optional[Dict]:
        """Get info for a specific slot."""
        for s in self.list_slots():
            if s.get("id") == slot_id:
                return s
        return None

    def add_slot(self, slot_id: str, name: str, description: str = "",
                 status: str = "active", project_count: int = 0) -> None:
        """Add a new slot to the registry."""
        data = self.load()
        # Remove existing entry if present
        data["slots"] = [s for s in data.get("slots", []) if s.get("id") != slot_id]
        data["slots"].append({
            "id": slot_id,
            "name": name,
            "description": description,
            "status": status,
            "created_at": datetime.now().isoformat(),
            "project_count": project_count,
        })
        self.save(data)

    def remove_slot(self, slot_id: str) -> bool:
        """Remove a slot from the registry. Returns True if removed."""
        data = self.load()
        original_count = len(data.get("slots", []))
        data["slots"] = [s for s in data.get("slots", []) if s.get("id") != slot_id]

        # Don't change active if it was removed
        if data.get("active_slot") == slot_id:
            data["active_slot"] = ""

        self.save(data)
        return len(data["slots"]) < original_count

    def update_slot_status(self, slot_id: str, status: str) -> None:
        """Update a slot's status."""
        data = self.load()
        for s in data.get("slots", []):
            if s.get("id") == slot_id:
                s["status"] = status
                break
        self.save(data)

    def get_next_slot_id(self) -> str:
        """Auto-generate the next slot ID (slot_xxx)."""
        data = self.load()
        max_idx = 0
        for s in data.get("slots", []):
            sid = s.get("id", "")
            if sid.startswith("slot_"):
                try:
                    idx = int(sid.replace("slot_", ""))
                    if idx > max_idx:
                        max_idx = idx
                except ValueError:
                    pass
        return f"slot_{max_idx + 1:03d}"

    def is_initialized(self) -> bool:
        """Check if workspace is properly initialized."""
        if not self.registry_file.exists():
            return False
        data = self.load()
        return (
            "active_slot" in data
            and "slots" in data
            and "version" in data
        )
