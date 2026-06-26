"""
test_ingest_appearance.py — CODE_REVIEW #19（部分修）

_count_character_appearances 的 longest-first + span 掩码计数：
消除『名字套名字』误计（Mode A）。Mode B（单字/常用字撞普通词）仍是已知局限。
"""
from src.pipeline.ingest import _count_character_appearances


def test_disjoint_names_match_str_count():
    # 互不为子串的常规名集 → 与 str.count 完全一致
    content = "张三走进屋，李四正在喝茶。张三看了李四一眼。"
    counts = _count_character_appearances(content, ["张三", "李四"])
    assert counts["张三"] == content.count("张三") == 2
    assert counts["李四"] == content.count("李四") == 2


def test_name_inside_longer_name_not_miscounted():
    # Mode A 核心：王明 出现在 王明月 中不被误计
    content = "王明月走来，王明月又走，王明独自离开"
    counts = _count_character_appearances(content, ["王明", "王明月"])
    assert counts["王明月"] == 2
    assert counts["王明"] == 1   # 仅末句那次真正的「王明」


def test_multiple_independent_appearances():
    content = "赵云出场，赵云再出场，赵云第三次出场"
    counts = _count_character_appearances(content, ["赵云"])
    assert counts["赵云"] == 3


def test_absent_character_is_zero():
    counts = _count_character_appearances("满篇都是别人", ["从未出现"])
    assert counts["从未出现"] == 0


def test_empty_inputs_do_not_crash():
    assert _count_character_appearances("", ["张三"]) == {"张三": 0}
    assert _count_character_appearances("正文", []) == {}
    # 空名被跳过，不计入结果键以外的统计；空串 name 视作未命中
    assert _count_character_appearances("正文", [""]) == {"": 0}


def test_mode_b_single_char_collision_excluded():
    # Mode B 边界启发式：单字名撞普通词（行李/桃李）被排除，不再误计为出场。
    content = "他提起行李，桃李满天下"
    counts = _count_character_appearances(content, ["李"])
    assert counts["李"] == 0   # 行李 + 桃李 均为撞词，非真实出场


def test_mode_b_real_single_char_mentions_counted():
    # 单字名真实出场（右侧人物动词）被正确计数。
    content = "「在吗？」李问道。李点头离开。"
    assert _count_character_appearances(content, ["李"])["李"] == 2


def test_mode_b_single_char_object_after_function_word():
    # 左侧虚词（把）锚定的宾语位单字名被计数。
    assert _count_character_appearances("我把李叫来。", ["李"])["李"] == 1


def test_mode_b_single_char_punctuation_boundary():
    assert _count_character_appearances("，李。", ["李"])["李"] == 1


def test_mode_b_mixed_collision_and_real_mention():
    # 行李 排除、李说 计入 → 净计 1。
    content = "行李很重，李说他来拿。"
    assert _count_character_appearances(content, ["李"])["李"] == 1
