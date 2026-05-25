#!/usr/bin/env python3
"""
bridge_evidence_guard.py — Continuity Bridge Evidence Guard v0.4.5

Problem: v0.4.0 continuity check scores by word overlap — "通铺房里",
"二十多个" — punishing chapters that change scene/location naturally.

Solution: Score continuity by EVIDENCE of bridge between chapters:
  1. ending_action:  does Ch N+1 open by continuing Ch N's final action?
  2. unresolved_hook:  does Ch N+1 address Ch N's hooks?
  3. character_state:  do physical/emotional states carry across?
  4. object_or_task:   do key objects, tasks, punishments persist?
  5. cast_continuity:  do key characters remain influential?

Scoring: >= 10 PASS, 6-9 WARN, <= 5 FAIL. Word overlap is NOT required.
"""

import json
import re
from pathlib import Path
from typing import Optional


MAX_SCORE = 15


def count_chinese(text: str) -> int:
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


def run_bridge_evidence_check(
    current_content: str,
    prev_tail: str = "",
    prev_brief: dict = None,
    prev_hooks: list[str] = None,
    task_card: dict = None,
    chapter_no: int = 0,
) -> dict:
    """
    Score continuity between previous chapter and current chapter.

    Args:
        current_content: full text of current chapter
        prev_tail: last 400-800 chars of previous chapter
        prev_brief: previous chapter's brief (ending_state, hooks)
        prev_hooks: explicit hook strings from previous chapter
        task_card: current chapter's task card (continuity_from_previous)
        chapter_no: current chapter number
    """
    prev_brief = prev_brief or {}
    prev_hooks = prev_hooks or []
    task_card = task_card or {}

    first_1200 = current_content[:1200]
    first_2000 = current_content[:2000]
    first_line = current_content.split("\n")[0] if current_content else ""

    score = 0
    evidence = []
    issues = []

    # ═══ 1. ending_action bridge (0-4 points) ═══
    # Check if current chapter's opening continues previous chapter's ending
    ending_state = prev_brief.get("ending_state", "")
    ending_action_keywords = _extract_action_keywords(prev_tail[-400:] if prev_tail else "")

    action_score = 0
    for kw in ending_action_keywords:
        if kw in first_1200:
            action_score += 1
            evidence.append(f"ending_action: '{kw}' carried to Ch{chapter_no}")
    action_score = min(4, action_score)
    score += action_score

    # ═══ 2. unresolved_hook bridge (0-4 points) ═══
    hooks = prev_brief.get("next_chapter_hooks", []) or prev_hooks
    if isinstance(hooks, str):
        hooks = [hooks]

    hook_score = 0
    hook_keywords = set()
    for hook in hooks:
        hook_keywords.update(_extract_key_nouns(hook))

    for kw in hook_keywords:
        if kw in first_2000:
            hook_score += 1
            evidence.append(f"hook: '{kw}' addressed in Ch{chapter_no}")
        elif task_card.get("continuity_from_previous", "") and kw in str(task_card):
            hook_score += 0.5
            evidence.append(f"hook: '{kw}' in task_card (planned)")

    hook_score = min(4, int(hook_score))
    score += hook_score
    if hook_score < 2 and hooks:
        issues.append(f"上章钩子({len(hooks)}条)在本章前半未见承接")

    # ═══ 3. character_state bridge (0-3 points) ═══
    # Physical injuries, emotional states, social positions
    state_continuity = _check_state_continuity(prev_tail, current_content)
    score += state_continuity
    if state_continuity >= 1:
        evidence.append(f"character_state: {state_continuity} states carried")
    else:
        issues.append("人物身体/情绪状态未延续")

    # ═══ 4. object/task bridge (0-2 points) ═══
    obj_score = _check_object_continuity(prev_tail, current_content)
    score += obj_score
    if obj_score >= 1:
        evidence.append(f"object/task: {obj_score} items persist")
    else:
        issues.append("关键物件/任务未在新章节出现")

    # ═══ 5. cast_continuity (0-2 points) ═══
    cast_score = _check_cast_continuity(prev_tail, current_content)
    score += cast_score
    if cast_score >= 1:
        evidence.append(f"cast: {cast_score} characters carry influence")

    # ═══ Final ═══
    if score >= 10:
        status = "PASS"
    elif score >= 6:
        status = "WARN"
    else:
        status = "FAIL"

    return {
        "guard": "bridge_evidence_guard",
        "status": status,
        "score": score,
        "max_score": MAX_SCORE,
        "evidence": evidence,
        "issues": issues,
        "detail": {
            "ending_action": action_score,
            "unresolved_hook": hook_score,
            "character_state": state_continuity,
            "object_task": obj_score,
            "cast_continuity": cast_score,
        },
        "hard_fail": False,
    }


def _extract_action_keywords(text: str) -> set[str]:
    """Extract action/motion keywords from text."""
    action_re = re.compile(
        r'(劈|砍|推|搬|拉|抬|抓|按|压|砸|走|跑|站|坐|躺|蹲|'
        r'说|问|答|叫|喊|笑|哭|看|盯|望|指|画|磨|擦|洗|煮|烧|'
        r'考核|验收|加.*[活捆量]|扣.*[饭分]|罚|记名|登记)')
    return set(m.group() for m in action_re.finditer(text))


def _extract_key_nouns(text: str) -> set[str]:
    """Extract key nouns that could be hooks."""
    noun_re = re.compile(
        r'(柴刀|水缸|石碑|矿[洞车石]|木牌|役牌|'
        r'考核|搬运|劈柴|灵矿|禁地|脉动|执事堂|'
        r'百分之一百二十|灰纸|规则|规矩|'
        r'[\u4e00-\u9fff]{2,3})')  # generic 2-3 char names
    return set(m.group() for m in noun_re.finditer(text))


def _check_state_continuity(prev_tail: str, current: str) -> int:
    """Check if physical/emotional states persist."""
    state_words = [
        "肿包", "血痂", "伤", "痛", "抖", "软", "闷",
        "恨", "怕", "怒", "忍", "沉默",
    ]
    score = 0
    for w in state_words:
        if w in prev_tail and w in current[:2000]:
            score += 1
    return min(3, score)


def _check_object_continuity(prev_tail: str, current: str) -> int:
    """Check if key objects persist."""
    objects = [
        "柴刀", "役牌", "树皮", "粗陶碗", "止血丸",
        "草鞋", "木牌", "石碑", "矿车", "考核",
        "灰纸", "劈柴", "粥", "水缸",
    ]
    score = 0
    for obj in objects:
        if obj in prev_tail and obj in current[:2000]:
            score += 1
    return min(2, score)


def _check_cast_continuity(prev_tail: str, current: str) -> int:
    """Check if key characters from previous chapter influence current."""
    # Generic: detect 2-4 char Chinese names using regex pattern
    name_matches = re.findall(r'(?:说|道|问|喊)[\s，。！？]*(?:[\u4e00-\u9fff]{2,4})', current[:2000])
    characters = list(set(re.findall(r'[\u4e00-\u9fff]{2,4}', ' '.join(name_matches))))[:7]
    score = 0
    for name in characters:
        if name in prev_tail and (name in current[:2000] or name in current):
            score += 1
    return min(2, score)


# ═══════════════════════════════════════════════════
# Guard-compatible entry
# ═══════════════════════════════════════════════════

def run_continuity_evidence_check(content: str, chapter_no: int,
                                  prev_tail: str = "",
                                  prev_brief: dict = None) -> dict:
    """
    Compatibility wrapper. Calls bridge_evidence_guard internally,
    but returns the old dict format for chapter_pipeline.py.
    """
    return run_bridge_evidence_check(
        current_content=content,
        prev_tail=prev_tail,
        prev_brief=prev_brief,
        chapter_no=chapter_no,
    )
