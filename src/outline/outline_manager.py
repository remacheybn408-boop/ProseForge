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
from src.db.registry import Registry
from src.utils.json_io import write_json_atomic


class OutlineManager:
    """大纲管理器：增删改查、版本管理、回滚"""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.workspace_dir = self.project_root / "workspace"
        self.registry = Registry(self.project_root)

    # ──────────────────────────────────────────────
    #  内部工具方法
    # ──────────────────────────────────────────────

    def _get_registry(self) -> Dict:
        """读取 workspace/registry.json"""
        return self.registry.load()
        rf = self.workspace_dir / "registry.json"
        if not rf.exists():
            return {"active_slot": "", "slots": []}
        return json.loads(rf.read_text(encoding="utf-8"))

    def _save_registry(self, data: Dict) -> None:
        self.registry.save(data)
        return
        rf = self.workspace_dir / "registry.json"
        rf.parent.mkdir(parents=True, exist_ok=True)
        rf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _get_active_slot(self) -> Optional[str]:
        return self.registry.get_active_slot()
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
        write_json_atomic(sf, data)
        return
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
        write_json_atomic(fp, data)
        return
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

    def _count_outline_structure(self, content: str) -> tuple[int, int]:
        """Count explicit Chinese volume/chapter headings in outline text."""
        import re

        volume_pattern = re.compile(r"^\s*第\s*[0-9一二三四五六七八九十百千万零〇]+\s*卷", re.MULTILINE)
        chapter_pattern = re.compile(r"^\s*第\s*[0-9一二三四五六七八九十百千万零〇]+\s*章", re.MULTILINE)
        volume_count = len(volume_pattern.findall(content))
        chapter_count = len(chapter_pattern.findall(content))
        return chapter_count, max(volume_count, 1)

    def _title_to_slug(self, title: str) -> str:
        """将标题转为 slug。委托 src.utils.slug.title_to_slug（全仓库唯一来源）。"""
        from src.utils.slug import title_to_slug
        return title_to_slug(title)

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
        自动生成 ID 和 metadata。如果当前没有 active slot 或活跃 slot 不对应该 title，
        会按 title 派生 slug 自动创建 / 切换到同名 slot。
        返回: {"id": ..., "title": ..., "created": True/False, "similarity": {...}, "slot": ...}
        """
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

        # 按 title 派生 slug 确保对应 slot 存在并设为 active
        # （v0.9.0：slot 按大纲名命名，替代 slot_001/002/003 数字序号）
        from src.db.slot_manager import SlotManager
        active = SlotManager(self.project_root).ensure_slot_for_outline(title)

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

        chapter_count, volume_count = self._count_outline_structure(content)

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

        # Insert novel row into slot's novels table
        try:
            from src.db._conn import connect_sqlite
            slot_dir = self._get_slot_dir(active)
            db_path = slot_dir / "novel.db"
            if db_path.exists():
                _slug = self._title_to_slug(title)
                _conn = connect_sqlite(db_path)
                _conn.execute(
                    "INSERT OR IGNORE INTO novels(slug, title, status) VALUES(?,?,?)",
                    (_slug, title, "planning")
                )
                _conn.commit()
                _conn.close()
        except Exception:
            pass

        # 自动提取角色关系
        self._auto_extract_relations(content, active)

        result = {
            "status": "ok",
            "id": outline_id,
            "title": title,
            "slot": active,
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

        from src.outline.similarity import OutlineSimilarity

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

        from src.outline.similarity import OutlineSimilarity

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

    # v0.9.0: 影子 slot 创建系统已移除。slot 命名统一由
    # src/db/slot_manager.py:ensure_slot_for_outline 负责（按大纲 title 派生 slug）。

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
        write_json_atomic(proj_file, proj)

        prev_data = json.loads(prev_file.read_text(encoding="utf-8"))
        return {
            "status": "ok",
            "message": f"已撤销到: {prev_data.get('title', prev_id)}",
            "removed": oid,
            "active": prev_id,
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
            return {"status": "error", "message": "没有活跃的工作区。请先运行 nf_初化 工具"}

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

            # 自动提取角色关系
            self._auto_extract_relations(content)

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

            # 自动提取角色关系
            self._auto_extract_relations(content)

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

    # ──────────────────────────────────────────────
    #  14. 角色关系自动提取
    # ──────────────────────────────────────────────

    def _auto_extract_relations(self, content: str, slot_id: str = None) -> int:
        """从大纲文本中自动提取角色关系并写入数据库。

        扫描关系关键词，识别角色间的关系类型：
        - "好友"/"朋友" → 友谊
        - "敌人"/"反派"/"对立" → 敌对
        - "师兄"/"师妹"/"师尊"/"弟子" → 师徒
        - "女主"/"女友"/"恋人"/"前世女友" → 恋人

        返回写入的关系数量。
        """
        import re as _re
        sid = slot_id or self._get_active_slot()
        if not sid:
            return 0

        # 1. 提取所有中文名
        surnames_str = ("李王张刘陈杨赵黄周吴徐孙马胡朱郭何林高罗"
                        "郑梁谢宋唐许邓韩冯曹彭曾肖田董潘袁蔡蒋余"
                        "于杜叶程苏魏吕丁任卢姚沈姜崔钟谭陆汪范金"
                        "石廖贾夏韦傅方白邹孟熊秦邱江尹薛阎段雷侯"
                        "龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤")
        surnames = set(surnames_str)
        _punct_chars = set("，。！？、；：""（）《》…— \t,./!?;:()[]{}")
        _bad_endings = {"场", "上", "下", "里", "前", "后", "中", "的", "了",
                        "和", "与", "在", "把", "被", "将", "对", "为",
                        "都", "也", "还", "就", "已", "能", "会", "可",
                        "来", "去", "出", "进", "到", "从", "以"}
        _stop_words = {"时候", "地方", "这里", "那里", "这边", "那边", "怎么", "什么",
                       "没有", "已经", "可以", "需要", "知道", "看见", "告诉", "开始",
                       "继续", "回到", "来到", "走出", "进入", "拿起", "放下"}
        _COMMON_COMPOUNDS = {
            "严禁", "严肃", "严重", "严格",
            "过程", "工程", "程度", "程序", "章程", "课程",
            "关于", "等于", "至于", "由于", "位于", "对于", "属于", "终于",
            "马上", "马路",
            "王国", "帝王", "霸王",
            "龙王", "巨龙", "恐龙", "神龙",
            "森林", "树林", "丛林", "园林", "密林",
            "资金", "金属", "现金", "黄金",
            "石头", "宝石", "钻石", "化石", "岩石",
            "方法", "方式", "方案", "方向", "方面",
            "高度", "高级", "高大", "高尚",
            "周围", "周期", "周年",
            "黄色", "黄昏",
            "江湖", "江山",
            "明白", "黑白", "洁白",
            "历史", "史书",
            "毛病", "毛发",
            "万物", "万事", "万一",
            "武器", "武功", "武术",
            "雷霆", "雷电",
            "段落", "手段", "阶段",
            "任何", "如何",
            "感谢", "谢谢",
            "苏醒", "复苏",
            "沉思", "沉重",
            "范围", "范例",
            "清楚", "清晰", "清醒", "清理",
            "叶子", "树叶",
        }

        reliable_names = set()
        for pattern in [r'(?:主角|姓名|角色|人物|男主|女主|男配|女配)[：:]\s*([^\n，。]{2,4})',
                        r'(?:主角|姓名|角色|人物|男主|女主|男配|女配)[是为叫作叫做称呼]\s*([^\n，。]{2,4})']:
            for m in _re.finditer(pattern, content):
                name = m.group(1).strip()
                if 2 <= len(name) <= 4:
                    reliable_names.add(name)

        heuristic_names = set()
        for i, ch in enumerate(content):
            if ch in surnames and i + 1 < len(content):
                nxt = content[i + 1]
                if nxt not in _punct_chars:
                    candidate2 = content[i:i + 2]
                    if candidate2[1] not in _bad_endings and candidate2 not in _stop_words and candidate2 not in _COMMON_COMPOUNDS:
                        heuristic_names.add(candidate2)

        all_names = set(reliable_names)
        for hn in heuristic_names:
            if any(hn in rn or rn in hn for rn in reliable_names):
                continue
            if content.count(hn) < 2:
                continue
            all_names.add(hn)
        all_names = {n for n in all_names if 2 <= len(n) <= 4}
        if len(all_names) < 2:
            return 0

        # 2. 关系关键词映射
        RELATION_KEYWORDS = {
            "友谊": ["好友", "朋友", "挚友", "知己", "兄弟", "闺蜜", "至交", "死党"],
            "敌对": ["敌人", "反派", "对立", "仇人", "宿敌", "对手", "死敌", "对头"],
            "师徒": ["师兄", "师妹", "师尊", "弟子", "师父", "师姐", "师弟",
                    "师叔", "师伯", "徒儿", "师傅", "师侄", "师祖"],
            "恋人": ["女友", "前世女友", "恋人", "情侣", "道侣", "夫妻", "丈夫",
                    "妻子", "未婚妻", "未婚夫", "红颜知己"],
        }

        relations_found = []

        # 3. 扫描每个句子/段落，检测角色关系
        segments = _re.split(r'[。\n]', content)
        for seg in segments:
            seg = seg.strip()
            if len(seg) < 10:
                continue

            # 找出段落中出现的所有角色名
            names_in_seg = [n for n in all_names if n in seg]
            if len(names_in_seg) < 2:
                continue

            # 检查是否包含关系关键词
            for rel_type, keywords in RELATION_KEYWORDS.items():
                for kw in keywords:
                    if kw not in seg:
                        continue
                    # 找到关键词附近的角色名对
                    kw_pos = seg.find(kw)
                    for i, na in enumerate(names_in_seg):
                        for nb in names_in_seg[i + 1:]:
                            if na == nb:
                                continue
                            # 只添加尚未记录的关系（去重）
                            pair = tuple(sorted([na, nb]))
                            existing = any(
                                tuple(sorted([r[0], r[1]])) == pair and r[2] == rel_type
                                for r in relations_found
                            )
                            if not existing:
                                relations_found.append((na, nb, rel_type))
                    break  # 每段对每个关系类型只匹配一次

        if not relations_found:
            return 0

        # 4. 写入数据库
        from src.guards.human_texture.voice_diversity_guard import set_relation
        saved = 0
        for char_a, char_b, rel_type in relations_found:
            ok = set_relation(self.project_root, char_a, char_b, rel_type)
            if ok:
                saved += 1

        if saved > 0:
            print(f"  [OK] 自动识别 {saved} 条角色关系")
        return saved

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
