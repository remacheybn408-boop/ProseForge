"""
test_slot_delete_consolidation.py — CODE_REVIEW #18

delete_slot 默认走回收站（可恢复），仅 force=True 才永久硬删；活跃槽受保护。
"""
import shutil

import pytest

from src.db.slot_manager import SlotManager


@pytest.fixture
def mgr(tmp_path, project_root):
    root = tmp_path / "proj"
    root.mkdir()
    shutil.copytree(project_root / "database", root / "database")
    m = SlotManager(root)
    m.init_workspace()
    m.create_slot("s1", ensure_registry=True, name="t1", description="t1")
    m.create_slot("s2", ensure_registry=True, name="t2", description="t2")
    m.registry.set_active_slot("s2")  # s1 非活跃，可删
    return m


def test_delete_slot_default_routes_to_trash(mgr):
    res = mgr.delete_slot("s1")
    assert res["status"] == "ok"
    assert not mgr.slot_exists("s1")            # 已移出 workspace
    trash = mgr.list_trash()
    assert any(t["original_slot_id"] == "s1" for t in trash)  # 进了回收站，可恢复


def test_delete_slot_force_is_permanent(mgr):
    res = mgr.delete_slot("s1", force=True)
    assert res["status"] == "ok"
    assert res.get("removed_dir") is True
    assert not mgr.slot_exists("s1")
    assert mgr.list_trash() == []               # force 不进回收站


def test_delete_active_slot_protected(mgr):
    res = mgr.delete_slot("s2")                  # s2 是活跃槽
    assert res["status"] == "error"
    assert mgr.slot_exists("s2")                 # 未被删除
