#!/usr/bin/env python3
"""Test concrete_hook_guard — 具体钩子门禁测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from src.guards.concrete_hook_guard import run_concrete_hook_check, analyze_ending


def test_vague_hook_fails():
    """空泛危机句 → 检测"""
    content = "前面的内容省略...\n\n" * 5 + "周砚望向远方，真正的危机才刚刚开始。"
    report = run_concrete_hook_check(content, 1)
    assert report["vague_hook_found"] is True


def test_object_hook_passes():
    """物件锚点 → 通过"""
    content = "前面的内容省略...\n\n" * 5 + "碎铜钱里露出一根黑色的细线，像活物一样缓缓钻回矿壁之中。"
    report = run_concrete_hook_check(content, 1)
    assert "object" in report.get("anchor_types", [])


def test_person_hook_passes():
    """人物锚点 → 通过"""
    content = "前面的内容省略...\n\n" * 5 + "门外站着的不是戒律堂弟子，而是三天前已经下葬的老矿头。"
    report = run_concrete_hook_check(content, 1)
    assert "person" in report.get("anchor_types", [])


def test_relationship_hook_passes():
    """关系锚点 → 通过"""
    content = "前面的内容省略...\n\n" * 5 + "师姐把剑横在他喉前，声音很轻：'你刚才用的，不是本门术法。'"
    report = run_concrete_hook_check(content, 1)
    assert "relationship" in report.get("anchor_types", [])


def test_cost_hook_passes():
    """代价锚点 → 通过"""
    content = "前面的内容省略...\n\n" * 5 + "灵压散去后，他终于看懂了矿壁上的纹路，却发现自己记不起母亲的名字了。"
    report = run_concrete_hook_check(content, 1)
    assert "cost" in report.get("anchor_types", [])


def test_no_hook_warning():
    """无任何锚点 → WARNING"""
    content = "这是普通的一段结尾。天气不错。他收拾好东西准备离开。"
    report = run_concrete_hook_check(content, 1)
    # 没有具体锚点
    assert report["anchor_count"] == 0
    assert report["concrete_hook_pass"] is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
