#!/usr/bin/env python3
"""
slot_manager.py — DB Slot 生命周期管理 v0.6.5

管理单个 DB slot 的目录结构、创建、删除、备份和恢复。
支持自动创建 slot_004 当已有 3 个满 slot 时。
"""
import json
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

from scripts.db.registry import Registry


# Standard slot subdirectory structure
SLOT_SUBDIRS = ["outlines", "chapters", "reports", "exports", "backups"]


class SlotManager:
    """Manages the lifecycle of individual DB slots."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.workspace_dir = self.project_root / "workspace"
        self.registry = Registry(project_root)

    # === P0-4: Per-slot novel.db helpers ===

    def get_slot_db_path(self, slot_id: str) -> Path:
        """Get the novel.db path for a given slot."""
        return self.get_slot_dir(slot_id) / "novel.db"

    def get_active_db_path(self) -> Optional[Path]:
        """Get the novel.db path for the currently active slot."""
        active = self.registry.get_active_slot()
        if not active:
            return None
        return self.get_slot_db_path(active)

    def _init_slot_db(self, slot_dir: Path) -> None:
        """Create and initialize a novel.db inside a slot directory with core tables."""
        db_path = slot_dir / "novel.db"
        conn = sqlite3.connect(str(db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS novels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    genre TEXT DEFAULT '',
                    theme TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    target_words INTEGER DEFAULT 0,
                    current_words INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'planning',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT DEFAULT 'note',
                    project TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    importance INTEGER DEFAULT 3,
                    source TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    last_used_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS volumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER NOT NULL,
                    title TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    target_words INTEGER DEFAULT 0,
                    UNIQUE(novel_id, volume_no)
                );

                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_id INTEGER REFERENCES volumes(id),
                    chapter_no INTEGER NOT NULL,
                    title TEXT DEFAULT '',
                    content TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    word_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    file_path TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, chapter_no)
                );

                CREATE TABLE IF NOT EXISTS chapter_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER NOT NULL REFERENCES chapters(id),
                    chunk_no INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    word_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    name TEXT NOT NULL,
                    alias TEXT DEFAULT '',
                    role TEXT DEFAULT '',
                    identity TEXT DEFAULT '',
                    personality TEXT DEFAULT '',
                    motivation TEXT DEFAULT '',
                    ability TEXT DEFAULT '',
                    relationship TEXT DEFAULT '',
                    arc TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    tags TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS worldbuilding (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    category TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    importance INTEGER DEFAULT 3,
                    tags TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS plot_threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    thread_type TEXT DEFAULT '伏笔',
                    introduced_chapter INTEGER,
                    resolved_chapter INTEGER,
                    status TEXT DEFAULT 'open',
                    importance INTEGER DEFAULT 3
                );

                CREATE TABLE IF NOT EXISTS writing_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    rule_type TEXT DEFAULT 'other',
                    importance INTEGER DEFAULT 3,
                    status TEXT DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS chapter_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER NOT NULL REFERENCES chapters(id),
                    short_summary TEXT DEFAULT '',
                    long_summary TEXT DEFAULT '',
                    key_events TEXT DEFAULT '',
                    characters_involved TEXT DEFAULT '',
                    new_settings TEXT DEFAULT '',
                    foreshadowing TEXT DEFAULT '',
                    continuity_notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, chapter_id)
                );

                CREATE TABLE IF NOT EXISTS continuity_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER NOT NULL REFERENCES chapters(id),
                    check_type TEXT DEFAULT 'continuity',
                    issue TEXT DEFAULT '',
                    suggestion TEXT DEFAULT '',
                    severity INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'open',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS novel_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    target_type TEXT,
                    target_id INTEGER,
                    detail TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS chapter_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER,
                    chapter_no INTEGER NOT NULL,
                    version_no INTEGER NOT NULL DEFAULT 1,
                    version_status TEXT DEFAULT 'draft',
                    title TEXT DEFAULT '',
                    content TEXT NOT NULL,
                    word_count INTEGER DEFAULT 0,
                    change_reason TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS reader_promises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    promise_title TEXT NOT NULL,
                    promise_detail TEXT NOT NULL,
                    introduced_chapter INTEGER,
                    expected_payoff_range TEXT DEFAULT '',
                    payoff_chapter INTEGER,
                    status TEXT DEFAULT 'open',
                    importance INTEGER DEFAULT 3,
                    reader_emotion TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS volume_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER NOT NULL,
                    planned_title TEXT DEFAULT '',
                    final_title TEXT DEFAULT '',
                    title_status TEXT DEFAULT 'planned',
                    suggested_chapters INTEGER DEFAULT 25,
                    min_chapters INTEGER DEFAULT 20,
                    max_chapters INTEGER DEFAULT 29,
                    volume_goal TEXT DEFAULT '',
                    opening_state TEXT DEFAULT '',
                    ending_target TEXT DEFAULT '',
                    must_complete TEXT DEFAULT '',
                    unresolved_hooks_to_next TEXT DEFAULT '',
                    outline_version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, volume_no)
                );

                CREATE TABLE IF NOT EXISTS chapter_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER NOT NULL,
                    chapter_no INTEGER NOT NULL,
                    planned_title TEXT DEFAULT '',
                    final_title TEXT DEFAULT '',
                    title_status TEXT DEFAULT 'planned',
                    plan_status TEXT DEFAULT 'planned',
                    chapter_goal TEXT DEFAULT '',
                    main_event TEXT DEFAULT '',
                    character_focus TEXT DEFAULT '',
                    conflict_point TEXT DEFAULT '',
                    must_include TEXT DEFAULT '',
                    plot_threads_to_advance TEXT DEFAULT '',
                    reader_promises_to_advance TEXT DEFAULT '',
                    ending_hook_direction TEXT DEFAULT '',
                    continuity_from_previous TEXT DEFAULT '',
                    title_change_reason TEXT DEFAULT '',
                    actual_word_count INTEGER DEFAULT 0,
                    actual_summary TEXT DEFAULT '',
                    completion_status TEXT DEFAULT '',
                    ingested_at TEXT DEFAULT '',
                    outline_version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, volume_no, chapter_no)
                );

                CREATE TABLE IF NOT EXISTS title_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER,
                    chapter_no INTEGER,
                    old_title TEXT DEFAULT '',
                    new_title TEXT DEFAULT '',
                    title_type TEXT DEFAULT 'chapter',
                    change_reason TEXT DEFAULT '',
                    changed_at TEXT DEFAULT (datetime('now'))
                );

                -- FTS5 全文检索索引 (v0.6.5-clean3)
                CREATE VIRTUAL TABLE IF NOT EXISTS novel_chapter_fts USING fts5(
                    title, content, summary,
                    content='chapters', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_chunk_fts USING fts5(
                    content, summary,
                    content='chapter_chunks', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_character_fts USING fts5(
                    name, alias, identity, personality, tags,
                    content='characters', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_world_fts USING fts5(
                    title, content, tags,
                    content='worldbuilding', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_plot_fts USING fts5(
                    title, content,
                    content='plot_threads', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    title, content, tags,
                    content='memories', content_rowid='id'
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def migrate_slot_fts(self, slot_id: str) -> bool:
        """Ensure a slot's novel.db has FTS5 tables (idempotent migration, v0.6.5-clean3)."""
        import sqlite3
        db_path = self.get_slot_db_path(slot_id)
        if not db_path.exists():
            return False
        conn = sqlite3.connect(str(db_path))
        try:
            conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS novel_chapter_fts USING fts5(
                    title, content, summary,
                    content='chapters', content_rowid='id'
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS novel_chunk_fts USING fts5(
                    content, summary,
                    content='chapter_chunks', content_rowid='id'
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS novel_character_fts USING fts5(
                    name, alias, identity, personality, tags,
                    content='characters', content_rowid='id'
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS novel_world_fts USING fts5(
                    title, content, tags,
                    content='worldbuilding', content_rowid='id'
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS novel_plot_fts USING fts5(
                    title, content,
                    content='plot_threads', content_rowid='id'
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    title, content, tags,
                    content='memories', content_rowid='id'
                );
            """)
            conn.commit()
            return True
        finally:
            conn.close()

    def get_slot_dir(self, slot_id: str) -> Path:
        """Get the directory path for a slot."""
        return self.workspace_dir / slot_id

    def slot_exists(self, slot_id: str) -> bool:
        """Check if a slot directory exists."""
        return self.get_slot_dir(slot_id).exists()

    def init_workspace(self, force: bool = False) -> Dict:
        """
        Initialize the workspace with registry and 3 default slots.
        Returns a status dict.
        """
        result = {"status": "ok", "created": [], "message": ""}

        if self.registry.exists() and not force:
            result["status"] = "already_initialized"
            result["message"] = "workspace/ 已经初始化"
            return result

        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Initialize registry
        registry_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "active_slot": "slot_001",
            "slots": [
                {
                    "id": "slot_001",
                    "name": "默认工作区",
                    "description": "默认项目工作区",
                    "status": "active",
                    "created_at": datetime.now().isoformat(),
                    "project_count": 0,
                }
            ],
        }
        self.registry.save(registry_data)
        result["created"].append("registry.json")

        # Create 3 initial slots (all 3 get directories + novel.db, none auto-register)
        for i in range(1, 4):
            slot_id = f"slot_{i:03d}"
            self.create_slot(slot_id, ensure_registry=False)
            result["created"].append(slot_id)

        # P0-5: Register all 3 slots in registry.
        # slot_001 is already in the initial registry JSON above (status=active).
        # slot_002 and slot_003 need explicit registration as normal/idle slots.
        self.registry.add_slot(
            slot_id="slot_002",
            name="空闲工作区 2",
            description="空闲工作区",
            status="normal",
            project_count=0,
        )
        self.registry.add_slot(
            slot_id="slot_003",
            name="空闲工作区 3",
            description="空闲工作区",
            status="normal",
            project_count=0,
        )

        # P0-1 clean3: Migrate all slot DBs to include FTS5 tables
        for i in range(1, 4):
            slot_id = f"slot_{i:03d}"
            self.migrate_slot_fts(slot_id)

        result["message"] = f"workspace 初始化完成，创建了 {len(result['created'])-1} 个 slot"
        return result

    def create_slot(self, slot_id: str, ensure_registry: bool = True,
                    name: str = "", description: str = "") -> Dict:
        """
        Create a new slot directory and its structure.
        Returns dict with slot info.
        """
        slot_dir = self.get_slot_dir(slot_id)
        slot_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        for subdir in SLOT_SUBDIRS:
            (slot_dir / subdir).mkdir(parents=True, exist_ok=True)

        # P0-4: Create per-slot novel.db with full schema
        self._init_slot_db(slot_dir)

        # Create project.json
        slot_name = name or slot_id.replace("_", " ").title()
        proj_data = {
            "name": slot_name,
            "title": slot_name,
            "active_outline": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        proj_file = slot_dir / "project.json"
        proj_file.write_text(
            json.dumps(proj_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Add to registry
        if ensure_registry:
            self.registry.add_slot(
                slot_id=slot_id,
                name=slot_name,
                description=description,
                status="active",
                project_count=1,
            )

        return {
            "id": slot_id,
            "name": slot_name,
            "dir": str(slot_dir),
            "created": True,
        }

    def create_slot_auto(self, name: str, description: str = "") -> Dict:
        """
        Auto-create a new slot with auto-generated ID.
        Auto-creates slot_004 when 3 slots exist but slot_004 is missing.
        """
        slots = self.registry.list_slots()
        slot_count = len(slots)

        # Auto-create slot_004 if needed (when 3 full slots exist)
        if slot_count >= 3:
            existing_ids = {s.get("id") for s in slots}
            # Ensure slots 1-3 exist if count >= 3
            for i in range(1, 4):
                sid = f"slot_{i:03d}"
                if sid not in existing_ids and not self.slot_exists(sid):
                    self.create_slot(sid)

        slot_id = self.registry.get_next_slot_id()
        return self.create_slot(slot_id, ensure_registry=True,
                                name=name, description=description)

    def delete_slot(self, slot_id: str) -> Dict:
        """
        Delete a slot (directory + registry entry).
        Protected: won't delete slot_001 or the active slot.
        """
        result = {"status": "ok", "message": ""}

        active = self.registry.get_active_slot()
        if slot_id == active:
            result["status"] = "error"
            result["message"] = f"不能删除当前活跃的 slot ({slot_id})"
            return result

        if slot_id == "slot_001":
            result["status"] = "error"
            result["message"] = "slot_001 是默认工作区，不能删除"
            return result

        # Remove from registry
        removed = self.registry.remove_slot(slot_id)

        # Remove directory
        slot_dir = self.get_slot_dir(slot_id)
        if slot_dir.exists():
            shutil.rmtree(slot_dir)
            result["message"] = f"Slot {slot_id} 已删除（目录和注册表）"
            result["removed_dir"] = True
        else:
            result["message"] = f"Slot {slot_id} 已从注册表移除（目录不存在）"
            result["removed_dir"] = False

        result["removed_registry"] = removed
        return result

    # === P1-3: Safe Delete with Trash ===

    def _get_trash_dir(self) -> Path:
        """Get the _trash directory path inside workspace."""
        return self.workspace_dir / "_trash"

    def delete_slot_safe(self, slot_id: str, confirm: bool = False) -> Dict:
        """
        Safe delete: move slot to workspace/_trash/ instead of permanently deleting.
        Protected: won't delete slot_001 or the active slot.
        Requires explicit confirm=True.

        The slot is moved to workspace/_trash/<timestamp>_<slot_id>/
        """
        result = {"status": "ok", "message": ""}

        if not confirm:
            result["status"] = "error"
            result["message"] = "必须确认删除操作（confirm=True）"
            return result

        active = self.registry.get_active_slot()
        if slot_id == active:
            result["status"] = "error"
            result["message"] = f"不能删除当前活跃的 slot ({slot_id})"
            return result

        if slot_id == "slot_001":
            result["status"] = "error"
            result["message"] = "slot_001 是默认工作区，不能删除"
            return result

        slot_dir = self.get_slot_dir(slot_id)
        if not slot_dir.exists():
            # Just remove from registry if dir doesn't exist
            self.registry.remove_slot(slot_id)
            result["status"] = "error"
            result["message"] = f"Slot {slot_id} 目录不存在，已从注册表移除"
            return result

        # Create trash directory with timestamp prefix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        trash_name = f"{timestamp}_{slot_id}"
        trash_dir = self._get_trash_dir()
        trash_dir.mkdir(parents=True, exist_ok=True)

        target = trash_dir / trash_name

        # Move the slot directory to trash
        try:
            shutil.move(str(slot_dir), str(target))
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"移动到回收站失败: {e}"
            return result

        # Record trash metadata
        meta_file = target / ".trash_meta.json"
        meta = {
            "original_slot_id": slot_id,
            "trashed_at": datetime.now().isoformat(),
            "trash_name": trash_name,
        }
        meta_file.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Remove from registry
        self.registry.remove_slot(slot_id)

        result["message"] = f"Slot {slot_id} 已移至回收站 (workspace/_trash/{trash_name})"
        result["trash_name"] = trash_name
        result["trash_path"] = str(target)
        return result

    def list_trash(self) -> List[Dict]:
        """List all items in the trash directory."""
        trash_dir = self._get_trash_dir()
        if not trash_dir.exists():
            return []

        items = []
        for entry in sorted(trash_dir.iterdir(), key=lambda p: p.name, reverse=True):
            if entry.is_dir():
                meta_file = entry / ".trash_meta.json"
                meta = {}
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        pass

                items.append({
                    "trash_name": entry.name,
                    "original_slot_id": meta.get("original_slot_id", entry.name.split("_", 2)[-1] if "_" in entry.name else entry.name),
                    "trashed_at": meta.get("trashed_at", datetime.fromtimestamp(entry.stat().st_mtime).isoformat()),
                    "size_bytes": sum(f.stat().st_size for f in entry.rglob("*") if f.is_file()),
                })

        return items

    def restore_slot_from_trash(self, trash_name: str) -> Dict:
        """
        Restore a slot from trash back to workspace.

        Args:
            trash_name: The trash directory name (e.g., '20260126_120000_slot_002')

        Returns:
            Result dict with status.
        """
        result = {"status": "ok", "message": ""}
        trash_dir = self._get_trash_dir()
        source = trash_dir / trash_name

        if not source.exists():
            result["status"] = "error"
            result["message"] = f"回收站中未找到: {trash_name}"
            available = [t["trash_name"] for t in self.list_trash()]
            if available:
                result["available"] = available
            return result

        # Determine original slot_id
        meta_file = source / ".trash_meta.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            slot_id = meta.get("original_slot_id", "")
        else:
            # Fallback: try to extract from trash_name format <timestamp>_<slot_id>
            parts = trash_name.split("_", 2)
            slot_id = parts[2] if len(parts) >= 3 else trash_name

        if not slot_id:
            result["status"] = "error"
            result["message"] = "无法确定原始 slot ID"
            return result

        # Check if slot_id directory already exists in workspace
        target = self.get_slot_dir(slot_id)
        if target.exists():
            result["status"] = "error"
            result["message"] = f"Slot {slot_id} 已存在于 workspace 中，无法覆盖恢复"
            return result

        # Move from trash back to workspace
        try:
            shutil.move(str(source), str(target))
        except Exception as e:
            result["status"] = "error"
            result["message"] = f"从回收站恢复失败: {e}"
            return result

        # Remove trash metadata file
        meta_target = target / ".trash_meta.json"
        if meta_target.exists():
            meta_target.unlink()

        # Re-register in registry
        proj_file = target / "project.json"
        slot_name = slot_id.replace("_", " ").title()
        if proj_file.exists():
            try:
                proj = json.loads(proj_file.read_text(encoding="utf-8"))
                slot_name = proj.get("name", proj.get("title", slot_name))
            except json.JSONDecodeError:
                pass

        self.registry.add_slot(
            slot_id=slot_id,
            name=slot_name,
            description=f"从回收站恢复 ({trash_name})",
            status="normal",
            project_count=1,
        )

        result["message"] = f"Slot {slot_id} 已从回收站恢复"
        result["slot_id"] = slot_id
        return result

    def purge_trash(self, trash_name: Optional[str] = None) -> Dict:
        """
        Permanently delete items from trash.

        Args:
            trash_name: Specific trash item to purge, or None to purge all.

        Returns:
            Result dict with status.
        """
        result = {"status": "ok", "message": "", "purged": []}
        trash_dir = self._get_trash_dir()

        if not trash_dir.exists():
            result["message"] = "回收站为空"
            return result

        if trash_name:
            target = trash_dir / trash_name
            if not target.exists():
                result["status"] = "error"
                result["message"] = f"回收站中未找到: {trash_name}"
                return result
            try:
                shutil.rmtree(str(target))
                result["purged"].append(trash_name)
                result["message"] = f"已永久删除: {trash_name}"
            except Exception as e:
                result["status"] = "error"
                result["message"] = f"永久删除失败: {e}"
        else:
            # Purge all
            purged_count = 0
            for entry in list(trash_dir.iterdir()):
                if entry.is_dir():
                    try:
                        shutil.rmtree(str(entry))
                        result["purged"].append(entry.name)
                        purged_count += 1
                    except Exception as e:
                        result.setdefault("errors", []).append({
                            "item": entry.name, "error": str(e)
                        })
            if result.get("errors"):
                result["status"] = "partial"
                result["message"] = f"已永久删除 {purged_count} 项，{len(result['errors'])} 项失败"
            else:
                result["message"] = f"已永久删除 {purged_count} 项"

        return result

    def backup_slot(self, slot_id: Optional[str] = None) -> Dict:
        """
        Backup a slot's project.json to its backup directory.
        Returns dict with backup info.
        """
        active = slot_id or self.registry.get_active_slot()
        if not active:
            return {"status": "error", "message": "无活跃 slot"}

        slot_dir = self.get_slot_dir(active)
        proj_file = slot_dir / "project.json"
        backup_dir = slot_dir / "backups"

        if not proj_file.exists():
            # Create project.json if missing
            self.create_slot(active)
            proj_file = slot_dir / "project.json"

        backup_dir.mkdir(parents=True, exist_ok=True)

        proj = json.loads(proj_file.read_text(encoding="utf-8"))
        proj["backed_up_at"] = datetime.now().isoformat()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"backup_{timestamp}.json"
        backup_file.write_text(
            json.dumps(proj, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return {
            "status": "ok",
            "slot_id": active,
            "backup_file": str(backup_file),
            "timestamp": timestamp,
        }

    def restore_slot(self, slot_id: str, backup_id: Optional[str] = None) -> Dict:
        """
        Restore a slot's project.json from backup.
        Returns dict with restore info.
        """
        slot_dir = self.get_slot_dir(slot_id)
        backup_dir = slot_dir / "backups"

        if not backup_dir.exists():
            return {"status": "error", "message": f"{slot_id} 没有备份目录"}

        backups = sorted(backup_dir.glob("backup_*.json"), reverse=True)
        if not backups:
            return {"status": "error", "message": f"{slot_id} 没有可用的备份文件"}

        # Find target backup
        target = backups[0]  # Default: latest
        if backup_id:
            found = [b for b in backups if backup_id in b.name]
            if not found:
                return {
                    "status": "error",
                    "message": f"未找到备份 {backup_id}",
                    "available": [b.name for b in backups],
                }
            target = found[0]

        # Restore
        backup_data = json.loads(target.read_text(encoding="utf-8"))
        proj_file = slot_dir / "project.json"
        proj_file.write_text(
            json.dumps(backup_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Update registry
        self.registry.update_slot_status(slot_id, "active")
        self.registry.add_slot(
            slot_id=slot_id,
            name=backup_data.get("name", backup_data.get("title", slot_id)),
            description=backup_data.get("description", ""),
            status="active",
        )

        return {
            "status": "ok",
            "slot_id": slot_id,
            "restored_from": target.name,
            "backup_time": datetime.fromtimestamp(
                target.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M"),
        }

    def ensure_slot_004(self) -> Optional[str]:
        """
        Ensure slot_004 exists when 3 slots are present.
        Auto-creates it if missing. Returns slot_id or None.
        """
        slots = self.registry.list_slots()
        if len(slots) >= 3:
            existing_ids = {s.get("id") for s in slots}
            if "slot_004" not in existing_ids and not self.slot_exists("slot_004"):
                result = self.create_slot("slot_004", ensure_registry=True,
                                          name="工作区 4")
                return result.get("id")
        return None

    def switch_to(self, slot_id: str) -> Dict:
        """
        Switch the active slot. Auto-registers if directory exists but not in registry.
        """
        slot_dir = self.get_slot_dir(slot_id)

        if not slot_dir.exists():
            return {
                "status": "error",
                "message": f"Slot {slot_id} 不存在",
                "available": [s.get("id") for s in self.registry.list_slots()],
            }

        # Auto-register if missing
        if not self.registry.get_slot(slot_id):
            self.registry.add_slot(slot_id, slot_id)

        old = self.registry.get_active_slot()
        self.registry.set_active_slot(slot_id)

        result = {"status": "ok", "slot_id": slot_id, "previous": old}

        # Load project info
        proj_file = slot_dir / "project.json"
        if proj_file.exists():
            proj = json.loads(proj_file.read_text(encoding="utf-8"))
            result["project"] = {
                "title": proj.get("title", proj.get("name", slot_id)),
                "outline": proj.get("active_outline", ""),
            }

        return result
