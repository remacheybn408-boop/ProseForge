#!/usr/bin/env python3
"""
outline_manager.py — 大纲管理器 v0.6.5

管理当前活跃 slot 下的大纲：
- 添加 / 导入 / 列出 / 查看 / 切换 / 对比 / 回滚 / 删除 / 分类
- 每个大纲存储为 JSON 文件，保存在 workspace/slots/<slot>/outlines/
- 支持 outline_versions 数组实现版本历史与回滚
- 通过 project.json 的 active_outline 字段标记当前激活大纲
- 所有输出使用中文
"""

import json
import shutil
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple


class OutlineManager:
    """大纲管理器：增删改查、版本管理、回滚"""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.workspace_dir = self.project_root / "workspace"

    # ──────────────────────────────────────────────
    #  内部工具方法
    # ──────────────────────────────────────────────

    def _get_registry(self) -> Dict:
        """读取 workspace/registry.json"""
        rf = self.workspace_dir / "registry.json"
        if not rf.exists():
            return {"active_slot": "", "slots": []}
        return json.loads(rf.read_text(encoding="utf-8"))

    def _save_registry(self, data: Dict) -> None:
        rf = self.workspace_dir / "registry.json"
        rf.parent.mkdir(parents=True, exist_ok=True)
        rf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_active_slot(self) -> Optional[str]:
        reg = self._get_registry()
        return reg.get("active_slot", "")

    def _get_slot_dir(self, slot_id: str = None) -> Path:
        sid = slot_id or self._get_active_slot()
        return self.workspace_dir / sid

    def _get_project_json(self, slot_id: str = None) -> Dict:
        sf = self._get_slot_dir(slot_id) / "project.json"
        if sf.exists():
            return json.loads(sf.read_text(encoding="utf-8"))
        return {
            "name": "未命名项目",
            "title": "未命名项目",
            "active_outline": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    def _save_project_json(self, data: Dict, slot_id: str = None) -> None:
        sf = self._get_slot_dir(slot_id) / "project.json"
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _outlines_dir(self, slot_id: str = None) -> Path:
        d = self._get_slot_dir(slot_id) / "outlines"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _read_outline_file(self, outline_id: str, slot_id: str = None) -> Optional[Dict]:
        fp = self._outlines_dir(slot_id) / f"{outline_id}.json"
        if not fp.exists():
            return None
        return json.loads(fp.read_text(encoding="utf-8"))

    def _write_outline_file(self, outline_id: str, data: Dict, slot_id: str = None) -> None:
        fp = self._outlines_dir(slot_id) / f"{outline_id}.json"
        fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _delete_outline_file(self, outline_id: str, slot_id: str = None) -> bool:
        fp = self._outlines_dir(slot_id) / f"{outline_id}.json"
        if fp.exists():
            fp.unlink()
            return True
        return False

    def _list_outline_ids(self, slot_id: str = None) -> List[str]:
        od = self._outlines_dir(slot_id)
        ids = []
        for f in sorted(od.glob("*.json")):
            if f.stem != ".gitkeep":
                ids.append(f.stem)
        return ids

    def _generate_outline_id(self, title: str = "") -> str:
        """根据标题生成简短ID"""
        import re
        base = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '_', title.lower().strip())
        base = base[:20] if base else "outline"
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{base}_{ts}"

    def _title_to_slug(self, title: str) -> str:
        """将中文标题转为拼音 slug（v0.6.5-clean6）"""
        import re, hashlib
        # 简单方案：取标题前8个中文字符的 MD5 前8位
        chinese = re.sub(r'[^\u4e00-\u9fff]', '', title)[:8]
        if chinese:
            return hashlib.md5(chinese.encode()).hexdigest()[:8]
        # 纯英文/数字
        clean = re.sub(r'[^a-z0-9]', '_', title.lower().strip())[:20]
        return clean or "novel"

    def _snapshot_version(self, old_data: Dict) -> List[Dict]:
        """创建一个版本快照，追加到版本历史"""
        versions = old_data.get("outline_versions", [])
        snapshot = {
            "version": len(versions) + 1,
            "title": old_data.get("title", ""),
            "content": old_data.get("content", ""),
            "tags": old_data.get("tags", []),
            "genre": old_data.get("genre", ""),
            "style": old_data.get("style", ""),
            "chapter_count": old_data.get("chapter_count", 0),
            "volume_count": old_data.get("volume_count", 1),
            "saved_at": datetime.now().isoformat(),
        }
        versions.append(snapshot)
        return versions

    # ──────────────────────────────────────────────
    #  1. 添加大纲
    # ──────────────────────────────────────────────

    def add_outline(self, content: str, title: str = "",
                    genre: str = "", style: str = "",
                    tags: list = None,
                    similarity_result: Dict = None) -> Dict:
        """
        添加新大纲（从文本内容）。
        自动生成 ID 和 metadata。
        返回: {"id": ..., "title": ..., "created": True/False, "similarity": {...}}
        """
        active = self._get_active_slot()
        if not active:
            return {"status": "error", "message": "没有活跃的工作区。请先运行 python novel.py db init"}

        # 提取标题（优先使用传入标题，其次从文本内容智能提取）
        if not title:
            for line in content.strip().split("\n"):
                raw = line.strip()
                # Skip empty lines and pure markdown headers
                if not raw:
                    continue
                # Pattern: 《书名》or # 《书名》
                import re as _re
                m = _re.search(r'[《「](.+?)[》」]', raw)
                if m:
                    title = m.group(1)[:40]
                    break
                # Pattern: 标题: xxx or 标题：xxx or 书名: xxx or 书名：xxx or 小说名: xxx
                m = _re.match(r'(标题|书名|小说名|作品名)[：:]\s*', raw)
                if m:
                    title = raw[m.end():].strip()[:40]
                    break
                # Pattern: # 开头（含空格）
                if raw.startswith('#'):
                    title = raw.lstrip('#').strip()[:40]
                    if title:
                        break
                    continue
                # Fallback: first non-empty, non-hash line
                title = raw[:40]
                break
        if not title:
            title = "未命名大纲"

        outline_id = self._generate_outline_id(title)

        # 解析章节数、卷数
        chapter_count = 0
        volume_count = 1
        for line in content.split("\n"):
            line = line.strip()
            if "第" in line and ("章" in line or "卷" in line):
                if "卷" in line:
                    # 粗略计数
                    pass
                if "章" in line:
                    chapter_count += 1

        data = {
            "id": outline_id,
            "title": title,
            "content": content,
            "tags": tags or [],
            "genre": genre,
            "style": style,
            "chapter_count": chapter_count,
            "volume_count": volume_count,
            "versions_count": 0,
            "outline_versions": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "source": "add",
        }

        if similarity_result:
            data["similarity_check"] = similarity_result

        self._write_outline_file(outline_id, data)

        # 自动设为激活大纲
        proj = self._get_project_json()
        proj["active_outline"] = outline_id
        proj["updated_at"] = datetime.now().isoformat()
        self._save_project_json(proj)

        result = {
            "status": "ok",
            "id": outline_id,
            "title": title,
            "created": True,
            "chapter_count": chapter_count,
            "volume_count": volume_count,
        }
        if similarity_result:
            result["similarity"] = similarity_result

        return result

    # ──────────────────────────────────────────────
    #  2. 导入大纲（指定标题）
    # ──────────────────────────────────────────────

    def import_outline(self, content: str, title: str,
                       genre: str = "", style: str = "",
                       tags: list = None) -> Dict:
        """导入大纲，需要指定标题"""
        return self.add_outline(
            content=content,
            title=title,
            genre=genre,
            style=style,
            tags=tags,
        )

    # ──────────────────────────────────────────────
    #  3. 列出所有大纲
    # ──────────────────────────────────────────────

    def list_outlines(self) -> List[Dict]:
        """列出当前 slot 所有大纲，含版本关系信息"""
        active = self._get_active_slot()
        if not active:
            return []

        proj = self._get_project_json()
        active_id = proj.get("active_outline", "")

        result = []
        for oid in self._list_outline_ids():
            data = self._read_outline_file(oid)
            if data:
                is_active = (oid == active_id)

                # ── 确定类型：active / historical / candidate ──
                outline_type = "candidate"
                if is_active:
                    outline_type = "active"
                elif data.get("outline_versions"):
                    outline_type = "historical"

                # ── 版本关系信息 ──
                versions = data.get("outline_versions", [])
                latest_version = versions[-1] if versions else None
                source_version = None
                if latest_version:
                    source_version = {
                        "version": latest_version.get("version"),
                        "title": latest_version.get("title", ""),
                        "saved_at": latest_version.get("saved_at", ""),
                    }

                # ── 相似度信息 ──
                similarity_info = data.get("similarity_check", None)
                similarity_score = None
                similar_to = None
                if similarity_info:
                    similarity_score = similarity_info.get("overall_score") or similarity_info.get("similarity")
                    similar_to = similarity_info.get("matched_outline") or similarity_info.get("matched_title")

                result.append({
                    "id": oid,
                    "title": data.get("title", ""),
                    "chapter_count": data.get("chapter_count", 0),
                    "volume_count": data.get("volume_count", 1),
                    "versions_count": len(versions),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "active": is_active,
                    "type": outline_type,
                    "genre": data.get("genre", ""),
                    "style": data.get("style", ""),
                    "tags": data.get("tags", []),
                    "source_version": source_version,
                    "similarity_score": similarity_score,
                    "similar_to": similar_to,
                    "source": data.get("source", "add"),
                })
        return result

    # ──────────────────────────────────────────────
    #  4. 当前大纲
    # ──────────────────────────────────────────────

    def current_outline(self) -> Optional[Dict]:
        """获取当前激活大纲"""
        active = self._get_active_slot()
        if not active:
            return None
        proj = self._get_project_json()
        oid = proj.get("active_outline")
        if not oid:
            return None
        data = self._read_outline_file(oid)
        if data:
            data["active"] = True
        return data

    # ──────────────────────────────────────────────
    #  5. 切换大纲
    # ──────────────────────────────────────────────

    def switch_outline(self, outline_id: str) -> Dict:
        """切换到指定大纲"""
        data = self._read_outline_file(outline_id)
        if not data:
            available = self._list_outline_ids()
            return {
                "status": "error",
                "message": f"大纲 {outline_id} 不存在",
                "available": available,
            }

        proj = self._get_project_json()
        old_id = proj.get("active_outline", "")
        proj["active_outline"] = outline_id
        proj["updated_at"] = datetime.now().isoformat()
        self._save_project_json(proj)

        return {
            "status": "ok",
            "outline_id": outline_id,
            "title": data.get("title", ""),
            "previous": old_id,
        }

    # ──────────────────────────────────────────────
    #  6. 对比两个大纲
    # ──────────────────────────────────────────────

    def diff_outlines(self, id1: str, id2: str) -> Dict:
        """对比两个已存储的大纲，调用相似度引擎"""
        d1 = self._read_outline_file(id1)
        d2 = self._read_outline_file(id2)

        if not d1:
            return {"status": "error", "message": f"大纲 {id1} 不存在"}
        if not d2:
            return {"status": "error", "message": f"大纲 {id2} 不存在"}

        from scripts.outline.similarity import OutlineSimilarity

        sim = OutlineSimilarity()
        result = sim.compare(
            title1=d1.get("title", ""),
            title2=d2.get("title", ""),
            content1=d1.get("content", ""),
            content2=d2.get("content", ""),
            genre1=d1.get("genre", ""),
            genre2=d2.get("genre", ""),
            style1=d1.get("style", ""),
            style2=d2.get("style", ""),
        )

        result["outline1"] = {"id": id1, "title": d1.get("title", "")}
        result["outline2"] = {"id": id2, "title": d2.get("title", "")}

        return result

    # ──────────────────────────────────────────────
    #  7. 回滚大纲到上一版本
    # ──────────────────────────────────────────────

    def rollback_outline(self, outline_id: str) -> Dict:
        """回滚大纲到上一个版本"""
        data = self._read_outline_file(outline_id)
        if not data:
            return {"status": "error", "message": f"大纲 {outline_id} 不存在"}

        versions = data.get("outline_versions", [])
        if len(versions) < 1:
            return {
                "status": "error",
                "message": f"大纲「{data.get('title', outline_id)}」没有可回滚的历史版本",
                "versions_count": 0,
            }

        # 取最后一个版本
        prev = versions.pop()
        old_title = data.get("title", "")
        old_content = data.get("content", "")

        # 恢复
        data["title"] = prev.get("title", old_title)
        data["content"] = prev.get("content", old_content)
        data["tags"] = prev.get("tags", data.get("tags", []))
        data["genre"] = prev.get("genre", data.get("genre", ""))
        data["style"] = prev.get("style", data.get("style", ""))
        data["chapter_count"] = prev.get("chapter_count", data.get("chapter_count", 0))
        data["volume_count"] = prev.get("volume_count", data.get("volume_count", 1))
        data["updated_at"] = datetime.now().isoformat()
        data["versions_count"] = len(versions)
        # 版本列表已移除最后一个
        data["outline_versions"] = versions

        self._write_outline_file(outline_id, data)

        return {
            "status": "ok",
            "outline_id": outline_id,
            "title": data["title"],
            "rolled_back_to": f"v{prev.get('version', '?')}",
            "saved_at": prev.get("saved_at", ""),
            "versions_remaining": len(versions),
        }

    # ──────────────────────────────────────────────
    #  8. 删除大纲
    # ──────────────────────────────────────────────

    def delete_outline(self, outline_id: str) -> Dict:
        """删除指定大纲"""
        data = self._read_outline_file(outline_id)
        if not data:
            return {"status": "error", "message": f"大纲 {outline_id} 不存在"}

        # 检查是否是当前激活大纲
        proj = self._get_project_json()
        active_id = proj.get("active_outline")

        self._delete_outline_file(outline_id)

        # 如果删除的是当前激活大纲，重置 active_outline
        if active_id == outline_id:
            remaining = self._list_outline_ids()
            next_active = remaining[0] if remaining else None
            proj["active_outline"] = next_active
            proj["updated_at"] = datetime.now().isoformat()
            self._save_project_json(proj)
            return {
                "status": "ok",
                "outline_id": outline_id,
                "title": data.get("title", ""),
                "deleted": True,
                "new_active": next_active,
            }

        return {
            "status": "ok",
            "outline_id": outline_id,
            "title": data.get("title", ""),
            "deleted": True,
        }

    # ──────────────────────────────────────────────
    #  9. 与文件对比
    # ──────────────────────────────────────────────

    def compare_with_file(self, file_path: str) -> Dict:
        """将当前激活大纲与外部文件对比"""
        fp = Path(file_path)
        if not fp.exists():
            return {"status": "error", "message": f"文件不存在: {file_path}"}

        current = self.current_outline()
        if not current:
            return {"status": "error", "message": "当前没有激活的大纲。请先添加大纲。"}

        file_content = fp.read_text(encoding="utf-8")

        from scripts.outline.similarity import OutlineSimilarity

        sim = OutlineSimilarity()
        result = sim.compare(
            title1=current.get("title", ""),
            title2=fp.stem,
            content1=current.get("content", ""),
            content2=file_content,
            genre1=current.get("genre", ""),
            genre2="",
            style1=current.get("style", ""),
            style2="",
        )

        result["outline1"] = {"id": current.get("id", ""), "title": current.get("title", "")}
        result["outline2"] = {"file": str(fp), "title": fp.stem}

        return result

    # ──────────────────────────────────────────────
    #  10. 检查是否有激活大纲
    # ──────────────────────────────────────────────

    def has_active_outline(self) -> bool:
        """检查当前 slot 是否有激活的大纲"""
        current = self.current_outline()
        return current is not None

    # ──────────────────────────────────────────────
    #  11. 更新大纲内容（带版本快照）
    # ──────────────────────────────────────────────

    def update_outline(self, outline_id: str, new_content: str,
                       title: str = "", genre: str = "", style: str = "",
                       tags: list = None) -> Dict:
        """更新大纲，自动创建版本快照"""
        old = self._read_outline_file(outline_id)
        if not old:
            return {"status": "error", "message": f"大纲 {outline_id} 不存在"}

        # 创建版本快照
        versions = self._snapshot_version(old)

        # 更新
        old["content"] = new_content
        old["tags"] = tags or old.get("tags", [])
        old["genre"] = genre or old.get("genre", "")
        old["style"] = style or old.get("style", "")
        if title:
            old["title"] = title
        old["outline_versions"] = versions
        old["versions_count"] = len(versions)
        old["updated_at"] = datetime.now().isoformat()

        # 重算章节数
        chapter_count = 0
        for line in new_content.split("\n"):
            if "第" in line and "章" in line:
                chapter_count += 1
        old["chapter_count"] = chapter_count

        self._write_outline_file(outline_id, old)

        return {
            "status": "ok",
            "outline_id": outline_id,
            "title": old["title"],
            "chapter_count": chapter_count,
            "versions_count": len(versions),
        }

    # ──────────────────────────────────────────────
    #  12. Slot 管理（用于 P0-6: 自动创建新 slot）
    # ──────────────────────────────────────────────

    def _find_idle_slot(self) -> Optional[str]:
        """查找空闲 slot（slot_002, slot_003）或返回 None。
        空闲 = slot 目录存在但没有 outlines/ 下的 .json 文件。
        """
        reg = self._get_registry()
        slots = reg.get("slots", [])
        active = reg.get("active_slot", "")

        for s in slots:
            sid = s.get("id", "")
            if sid == active:
                continue
            # Check if this slot is idle (no outlines)
            od = self._outlines_dir(sid)
            jsons = list(od.glob("*.json"))
            if not jsons or (len(jsons) == 1 and jsons[0].stem == ".gitkeep"):
                return sid
        return None

    def _get_next_slot_id(self) -> str:
        """自动生成下一个 slot ID（如 slot_004, slot_006 等）"""
        reg = self._get_registry()
        slots = reg.get("slots", [])
        max_idx = 0
        for s in slots:
            sid = s.get("id", "")
            if sid.startswith("slot_"):
                try:
                    idx = int(sid.replace("slot_", ""))
                    if idx > max_idx:
                        max_idx = idx
                except ValueError:
                    pass
        return f"slot_{max_idx + 1:03d}"

    def _create_slot_structure(self, slot_id: str, name: str = "", description: str = "") -> Path:
        """创建 slot 目录结构和 project.json + novel.db（v0.6.5-clean4: 统一建库）"""
        import sqlite3
        slot_dir = self.workspace_dir / slot_id
        slot_dir.mkdir(parents=True, exist_ok=True)
        for subdir in ["outlines", "chapters", "reports", "exports", "backups"]:
            (slot_dir / subdir).mkdir(parents=True, exist_ok=True)

        proj_file = slot_dir / "project.json"
        proj_data = {
            "name": name or slot_id,
            "title": name or "未命名项目",
            "active_outline": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        proj_file.write_text(json.dumps(proj_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # v0.6.5-clean4: 确保 novel.db 存在（含 FTS5 表）
        db_path = slot_dir / "novel.db"
        if not db_path.exists():
            conn = sqlite3.connect(str(db_path))
            try:
                # 委托 SlotManager._init_slot_db 的完整建库逻辑
                from scripts.db.slot_manager import SlotManager
                sm = SlotManager(self.project_root)
                sm._init_slot_db(slot_dir)
            except Exception:
                # Fallback: 内联建库（仅 core 表 + FTS5）
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
                    -- v0.6.5-clean4: FTS5 tables
                    CREATE VIRTUAL TABLE IF NOT EXISTS novel_chapter_fts USING fts5(
                        title, content, summary, content='chapters', content_rowid='id'
                    );
                    CREATE VIRTUAL TABLE IF NOT EXISTS novel_chunk_fts USING fts5(
                        content, summary, content='chapter_chunks', content_rowid='id'
                    );
                    CREATE VIRTUAL TABLE IF NOT EXISTS novel_character_fts USING fts5(
                        name, alias, identity, personality, tags, content='characters', content_rowid='id'
                    );
                    CREATE VIRTUAL TABLE IF NOT EXISTS novel_world_fts USING fts5(
                        title, content, tags, content='worldbuilding', content_rowid='id'
                    );
                    CREATE VIRTUAL TABLE IF NOT EXISTS novel_plot_fts USING fts5(
                        title, content, content='plot_threads', content_rowid='id'
                    );
                """)
                conn.commit()
            finally:
                conn.close()

        return slot_dir

    def _register_slot(self, slot_id: str, name: str = "", description: str = "") -> Dict:
        """在 registry.json 中注册新 slot 并返回更新后的 registry"""
        reg = self._get_registry()
        new_slot = {
            "id": slot_id,
            "name": name or slot_id,
            "description": description,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "project_count": 1,
        }
        # 检查是否已存在
        slots = reg.get("slots", [])
        existing = [s for s in slots if s.get("id") == slot_id]
        if not existing:
            slots.append(new_slot)
        else:
            existing[0].update(new_slot)
        reg["slots"] = slots
        self._save_registry(reg)
        return reg

    def undo_last_add(self) -> Dict:
        """v0.6.5-clean7: 撤销最近一次 outline add，恢复之前的状态."""
        reg = self._get_registry()
        active = reg.get("active_slot", "")
        if not active:
            return {"status": "error", "message": "没有活跃 slot"}

        proj_file = self.workspace_dir / active / "project.json"
        if not proj_file.exists():
            return {"status": "error", "message": "project.json 不存在"}

        proj = json.loads(proj_file.read_text(encoding="utf-8"))
        oid = proj.get("active_outline", "")
        if not oid:
            return {"status": "error", "message": "没有激活的大纲可撤销"}

        outlines_dir = self.workspace_dir / active / "outlines"
        outline_files = sorted(outlines_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if len(outline_files) < 2:
            return {"status": "error", "message": "只有一个大纲，无法撤销（需要至少两个版本）"}

        current_file = outlines_dir / f"{oid}.json"
        prev_file = outline_files[1]
        prev_id = prev_file.stem

        trash_dir = self.workspace_dir / "_trash"
        trash_dir.mkdir(exist_ok=True)
        import shutil
        shutil.move(str(current_file), str(trash_dir / current_file.name))

        proj["active_outline"] = prev_id
        proj["updated_at"] = datetime.now().isoformat()
        proj_file.write_text(json.dumps(proj, ensure_ascii=False, indent=2), encoding="utf-8")

        prev_data = json.loads(prev_file.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "message": f"已撤销到: {prev_data.get('title', prev_id)}",
            "removed": oid,
            "active": prev_id,
        }

    def _switch_active_slot(self, slot_id: str) -> str:
        """切换活跃 slot，返回旧的活跃 slot"""
        reg = self._get_registry()
        old = reg.get("active_slot", "")
        reg["active_slot"] = slot_id
        self._save_registry(reg)
        return old

    def add_outline_to_new_slot(self, content: str, title: str = "",
                                 genre: str = "", style: str = "",
                                 tags: list = None,
                                 similarity_result: Dict = None) -> Dict:
        """P0-6: 为新小说创建独立 slot 并导入大纲"""
        # 0. 如果没传标题，从内容提取
        if not title:
            for line in content.strip().split("\n"):
                raw = line.strip()
                if not raw: continue
                import re as _re
                m = _re.search(r'[《「](.+?)[》」]', raw)
                if m:
                    title = m.group(1)[:40]
                    break
            if not title:
                for line in content.strip().split("\n"):
                    raw = line.strip()
                    if not raw: continue
                    m = _re.match(r'^(?:标题[：:]|书名[：:]|小说名[：:]|作品名[：:])\s*(.+)', raw)
                    if m:
                        title = m.group(1).strip()[:40]
                        break
            if not title:
                for line in content.strip().split("\n"):
                    raw = line.strip()
                    if raw.startswith("# "):
                        t = raw[2:].strip()
                        # strip 《》if present
                        m2 = _re.search(r'[《「](.+?)[》」]', t)
                        title = (m2.group(1) if m2 else t)[:40]
                        break
        # 1. 寻找空闲 slot 或创建新的
        idle = self._find_idle_slot()
        if idle:
            slot_id = idle
            created_new = False
        else:
            slot_id = self._get_next_slot_id()
            created_new = True

        # 2. 创建 slot 结构
        slot_name = title or "未命名项目"
        slot_dir = self._create_slot_structure(slot_id, slot_name)
        self._register_slot(slot_id, slot_name, f"自动创建于相似度检测（低相似度）")

        # v0.6.5-clean6: 向 slot 的 novel.db 插入 novel 记录
        slug = self._title_to_slug(title) if title else slot_id
        db_path = slot_dir / "novel.db"
        if db_path.exists():
            import sqlite3 as _sql
            _conn = _sql.connect(str(db_path))
            try:
                _conn.execute(
                    "INSERT OR IGNORE INTO novels(slug, title, status) VALUES(?,?,?)",
                    (slug, title, "planning")
                )
                _conn.commit()
            finally:
                _conn.close()

        # 3. 导入大纲到新 slot
        outline_id = self._generate_outline_id(title)
        chapter_count = 0
        for line in content.split("\n"):
            if "第" in line and "章" in line:
                chapter_count += 1

        data = {
            "id": outline_id,
            "title": title,
            "content": content,
            "tags": tags or [],
            "genre": genre,
            "style": style,
            "chapter_count": chapter_count,
            "volume_count": 1,
            "versions_count": 0,
            "outline_versions": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "source": "add",
        }
        if similarity_result:
            data["similarity_check"] = similarity_result

        self._write_outline_file(outline_id, data, slot_id)

        # 设为激活大纲
        proj = self._get_project_json(slot_id)
        proj["active_outline"] = outline_id
        proj["updated_at"] = datetime.now().isoformat()
        self._save_project_json(proj, slot_id)

        # 4. 切换到新 slot
        old_slot = self._switch_active_slot(slot_id)

        return {
            "status": "ok",
            "slot_id": slot_id,
            "slot_created": created_new,
            "old_slot": old_slot,
            "outline_id": outline_id,
            "title": title,
            "chapter_count": chapter_count,
            "similarity": similarity_result,
        }

    def add_outline_as_version(self, content: str, title: str = "",
                                genre: str = "", style: str = "",
                                tags: list = None,
                                similarity_result: Dict = None,
                                activate: bool = False) -> Dict:
        """P0-7: 将新大纲作为当前 slot 的升级版本添加。
        
        Args:
            activate: 是否立即设为激活大纲（--replace-current）
        """
        active = self._get_active_slot()
        if not active:
            return {"status": "error", "message": "没有活跃的工作区。请先运行 python novel.py db init"}

        current = self.current_outline()

        if current and activate:
            # 替换模式：给当前大纲创建版本快照，然后更新内容
            old_data = current.copy()
            versions = self._snapshot_version(old_data)
            
            old_data["content"] = content
            if title:
                old_data["title"] = title
            old_data["genre"] = genre or old_data.get("genre", "")
            old_data["style"] = style or old_data.get("style", "")
            old_data["tags"] = tags or old_data.get("tags", [])
            old_data["outline_versions"] = versions
            old_data["versions_count"] = len(versions)
            old_data["updated_at"] = datetime.now().isoformat()
            old_data["source"] = "upgrade"
            if similarity_result:
                old_data["similarity_check"] = similarity_result

            # 重算章节数
            chapter_count = 0
            for line in content.split("\n"):
                if "第" in line and "章" in line:
                    chapter_count += 1
            old_data["chapter_count"] = chapter_count

            oid = current.get("id")
            self._write_outline_file(oid, old_data)

            return {
                "status": "ok",
                "mode": "replace",
                "id": oid,
                "title": old_data["title"],
                "chapter_count": chapter_count,
                "versions_count": len(versions),
                "similarity": similarity_result,
            }
        else:
            # 保存但不激活：添加为独立大纲（不设 active_outline）
            outline_id = self._generate_outline_id(title)
            chapter_count = 0
            for line in content.split("\n"):
                if "第" in line and "章" in line:
                    chapter_count += 1

            data = {
                "id": outline_id,
                "title": title,
                "content": content,
                "tags": tags or [],
                "genre": genre,
                "style": style,
                "chapter_count": chapter_count,
                "volume_count": 1,
                "versions_count": 0,
                "outline_versions": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "source": "upgrade_inactive",
            }
            if similarity_result:
                data["similarity_check"] = similarity_result

            self._write_outline_file(outline_id, data)
            # 不修改 active_outline，保留当前激活大纲不变

            return {
                "status": "ok",
                "mode": "inactive",
                "id": outline_id,
                "title": title,
                "chapter_count": chapter_count,
                "similarity": similarity_result,
            }

    # ──────────────────────────────────────────────
    #  13. 分类大纲：升级/同作/新作/需确认
    # ──────────────────────────────────────────────

    def classify_outline(self, outline_id: str) -> Dict:
        """获取大纲的分类信息"""
        data = self._read_outline_file(outline_id)
        if not data:
            return {"status": "error", "message": f"大纲 {outline_id} 不存在"}

        sc = data.get("similarity_check", None)

        info = {
            "id": outline_id,
            "title": data.get("title", ""),
            "genre": data.get("genre", ""),
            "style": data.get("style", ""),
            "chapter_count": data.get("chapter_count", 0),
            "volume_count": data.get("volume_count", 1),
            "created_at": data.get("created_at", ""),
            "versions_count": len(data.get("outline_versions", [])),
        }

        if sc:
            info["classification"] = sc.get("classification", "未知")
            info["similarity_score"] = sc.get("similarity_score", 0)
            info["recommendation"] = sc.get("recommendation", "未知")
            info["detail"] = sc.get("detail", {})

        return info
