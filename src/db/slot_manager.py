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

from src.db.init_db import ensure_db_schema, find_migrations, find_schema, init_db
from src.db.registry import Registry
from src.db._conn import connect_sqlite


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
        """Create and initialize a novel.db inside a slot directory with core tables.

        唯一权威来源是 database/schema.sql（含 migrations 回放）；该文件缺失时直接
        抛错，不再静默用内嵌 SQL 建一个缺迁移的库。
        """
        db_path = slot_dir / "novel.db"
        schema = find_schema(self.project_root)
        migrations = find_migrations(self.project_root)
        if schema is not None and init_db(db_path, schema, migrations):
            return
        schema_file = self.project_root / "database" / "schema.sql"
        if not schema_file.exists():
            raise FileNotFoundError(
                f"database/schema.sql 缺失，无法初始化 slot DB: {schema_file}"
            )
        conn = connect_sqlite(db_path)
        try:
            conn.executescript(schema_file.read_text(encoding="utf-8"))
            conn.commit()
        finally:
            conn.close()

    def ensure_slot_schema(self, slot_id: str) -> bool:
        """幂等地把一个已存在 slot 的 novel.db 补齐到当前完整 schema。

        用旧 schema 建的遗留库（缺 writing_rules 等表）调用本方法即可补齐，
        只加缺失的表、不动既有数据。库不存在时返回 False。复用 init_db 家族。
        """
        db_path = self.get_slot_db_path(slot_id)
        return ensure_db_schema(db_path, self.project_root)

    def migrate_slot_fts(self, slot_id: str) -> bool:
        """Ensure a slot's novel.db has FTS5 tables (idempotent migration, v0.6.5-clean3)."""
        import sqlite3
        db_path = self.get_slot_db_path(slot_id)
        if not db_path.exists():
            return False
        conn = connect_sqlite(db_path)
        try:
            conn.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS novel_chapter_fts USING fts5(
                    title, content, summary,
                    content='chapters', content_rowid='id'
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS novel_chunk_fts USING fts5(
                    content,
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
        Initialize the workspace: 仅创建 workspace/ 目录和空的 registry.json。
        不预创建任何 slot——第一次 `outline add` 会按大纲 title 派生 slug
        自动创建同名 slot（见 SlotManager.ensure_slot_for_outline）。
        """
        result = {"status": "ok", "created": [], "message": ""}

        if self.registry.exists() and not force:
            result["status"] = "already_initialized"
            result["message"] = "workspace/ 已经初始化"
            return result

        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        registry_data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "active_slot": "",
            "slots": [],
        }
        self.registry.save(registry_data)
        result["created"].append("registry.json")

        result["message"] = "workspace 初始化完成。请运行 nf_project outline add 导入大纲，将自动创建同名 slot"
        return result

    def init(self, force: bool = False) -> Dict:
        """Backward-compatible alias used by wrappers/plugins."""
        return self.init_workspace(force=force)

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
        Auto-create a new slot with auto-generated ID (timestamp-based fallback).
        新代码应优先用 ensure_slot_for_outline(title) 按大纲名命名。
        """
        slot_id = self.registry.get_next_slot_id()
        return self.create_slot(slot_id, ensure_registry=True,
                                name=name, description=description)

    @staticmethod
    def _title_to_slug(title: str) -> str:
        """委托 src.utils.slug.title_to_slug（全仓库唯一来源）。"""
        from src.utils.slug import title_to_slug
        return title_to_slug(title)

    def _slot_matches_title(self, slot_id: str, title: str) -> bool:
        """目标 slot 的 novel.db 是否已经存有该 title 的小说（用于判断能否复用）。"""
        db_path = self.get_slot_db_path(slot_id)
        if not db_path.exists():
            return True
        try:
            conn = connect_sqlite(db_path)
            try:
                cur = conn.execute("SELECT title FROM novels LIMIT 1")
                row = cur.fetchone()
                if row is None:
                    return True
                return row[0] == title
            finally:
                conn.close()
        except Exception:
            return False

    def ensure_slot_for_outline(self, title: str) -> str:
        """
        根据大纲 title 派生 slug，确保对应 slot 存在并设为 active slot。
        - 若同名 slot 不存在 → 创建。
        - 若同名 slot 已存在且其 novel.db 中 title 一致 → 复用。
        - 若同名 slot 已存在但 title 不同 → 加 _2 / _3 后缀直到不冲突。
        - title 为空或仅由特殊字符组成（slug 退化为 "novel"）时 →
          强制时间戳后缀，永不复用，避免不同空 title 的大纲互相覆盖。
        返回最终使用的 slot_id。
        """
        normalized_title = (title or "").strip()
        base = self._title_to_slug(title)

        # 空 title / 退化 slug：不复用，强制独立目录
        if not normalized_title or base == "novel":
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            candidate = f"novel_{ts}"
            self.create_slot(candidate, ensure_registry=True,
                             name=normalized_title or candidate,
                             description=normalized_title or candidate)
            self.registry.set_active_slot(candidate)
            return candidate

        existing_ids = {s.get("id") for s in self.registry.list_slots()}
        candidate = base
        n = 2
        while candidate in existing_ids and not self._slot_matches_title(candidate, title):
            candidate = f"{base}_{n}"
            n += 1

        if not self.slot_exists(candidate) or candidate not in existing_ids:
            self.create_slot(candidate, ensure_registry=True, name=title or candidate,
                             description=title or candidate)
        self.registry.set_active_slot(candidate)
        return candidate

    def delete_slot(self, slot_id: str) -> Dict:
        """
        Delete a slot (directory + registry entry).
        Protected: won't delete the active slot.
        """
        result = {"status": "ok", "message": ""}

        active = self.registry.get_active_slot()
        if slot_id == active:
            result["status"] = "error"
            result["message"] = f"不能删除当前活跃的 slot ({slot_id})"
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
        Protected: won't delete the active slot. Requires explicit confirm=True.

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
