#!/usr/bin/env python3
"""hallucination_guard.py — 幻觉拦截门禁

检查正文是否存在无依据新增或矛盾内容：
- 人物状态突变（境界/关系）
- 世界观设定凭空出现
- 上一章状态被遗忘（伤势/物品/任务）
- 伏笔被提前兑现
- 与任务卡/大纲冲突

用法:
  python scripts/hallucination_guard.py <chapter_text.txt> --task-card task.json --prev-summary prev.json
"""

import re, json, sys, argparse
from pathlib import Path


# ── 人物状态突变模式 ──
REALM_PATTERNS = [
    r'(突破|晋升|踏入|进阶).{0,10}(境界|层次|级别|阶段)',
    r'(成为|变成|化作).{0,10}(强者|高手|大师|宗师)',
    r'(修为|境界|实力).{0,10}(暴涨|飙升|突破|大增)',
]

RELATION_PATTERNS = [
    r'(忽然|突然|竟然).{0,5}(爱上|喜欢上|倾心)',
    r'(变成|成为).{0,5}(敌人|仇人|死敌)',
    r'(背叛|出卖|反水)',
]

FORGOTTEN_STATE_PATTERNS = [
    r'(伤口|伤势|受伤|流血)',
    r'(携带|拿着|背着|带着)',
    r'(任务|命令|嘱咐|交代)',
]

# ── 世界检测 ──
NEW_FACTION_PATTERNS = [
    r'(宗门|教派|组织|势力|帮派|世家)(.{2,8}?(?:出现|现身|降临|崛起|成立))',
    r'(从未听过|从未见过|闻所未闻)的(宗门|教派|势力)',
]

NEW_POWER_PATTERNS = [
    r'(领悟|掌握|觉醒|获得).{0,10}(新.{0,5}(功法|能力|力量|神通|方法|秘术|手段))',
    r'(发现|悟出|创出).{0,10}(修炼|功法|秘术|方法)',
]

# ── 伏笔/承诺 ──
PREMISE_PATTERNS = [
    r'(终于|总算|到底).{0,5}(恢复|找回|发现|突破|击败)',
    r'(伏笔|悬念|谜团).{0,5}(揭开|解开|揭晓|公布)',
]


def check_character_realm_shift(text, known_states):
    """检查人物境界是否突变。known_states: {name: {realm: str, last_seen_ch: int}}"""
    findings = []
    for pattern in REALM_PATTERNS:
        for m in re.finditer(pattern, text):
            context = text[max(0,m.start()-30):m.end()+30]
            findings.append({"type": "realm_shift", "text": m.group(), "context": context, "severity": "high"})
    return findings


def check_relation_shift(text, known_relations):
    """检查人物关系是否突变。known_relations: {pair: {status: str}}"""
    findings = []
    for pattern in RELATION_PATTERNS:
        for m in re.finditer(pattern, text):
            context = text[max(0,m.start()-30):m.end()+30]
            findings.append({"type": "relation_shift", "text": m.group(), "context": context, "severity": "high"})
    return findings


def check_new_canon(text, task_card, known_worldbuilding):
    """检查是否有未授权的新设定。task_card 允许的新设定不应拦截。"""
    findings = []
    allowed_topics = task_card.get("allowed_new_canon", []) if task_card else []

    for pattern in NEW_FACTION_PATTERNS + NEW_POWER_PATTERNS:
        for m in re.finditer(pattern, text):
            matched = m.group()
            # Check if this new canon is allowed by task card
            allowed = any(topic in matched for topic in allowed_topics)
            if not allowed:
                context = text[max(0,m.start()-30):m.end()+30]
                findings.append({
                    "type": "unauthorized_canon",
                    "text": matched,
                    "context": context,
                    "severity": "medium",
                    "allowed": False
                })
            else:
                findings.append({
                    "type": "allowed_new_canon",
                    "text": matched,
                    "context": "",
                    "severity": "info",
                    "allowed": True
                })
    return findings


def check_forgotten_state(text, prev_tail, prev_brief):
    """检查上一章的伤势/物品/任务是否被遗忘。"""
    findings = []
    if not prev_tail:
        return findings

    for pattern in FORGOTTEN_STATE_PATTERNS:
        prev_matches = re.findall(pattern, prev_tail[-500:])
        curr_matches = re.findall(pattern, text[:500])
        # If prev had a state marker that's absent in current, flag it
        for pm in prev_matches:
            if pm not in str(curr_matches):
                findings.append({
                    "type": "forgotten_state",
                    "text": pm,
                    "context": f"上章提及'{pm}'，本章开头未继承",
                    "severity": "low"
                })
    return findings


def check_contradictions(text, prev_summaries, known_facts):
    """检查是否与已知事实矛盾。"""
    findings = []
    
    # Check against known facts
    for fact in known_facts:
        if fact.get("negated_by"):
            for neg in fact["negated_by"]:
                if re.search(neg, text):
                    findings.append({
                        "type": "contradiction",
                        "text": f"与已知事实矛盾: {fact['fact']}",
                        "context": f"正文出现'{neg}'",
                        "severity": "critical"
                    })
    return findings


def check_premature_payoff(text, chapter_no, plot_threads, reader_promises):
    """检查伏笔/承诺是否被提前兑现。"""
    findings = []
    
    for thread in plot_threads:
        expected_ch = thread.get("expected_payoff_chapter", 999)
        if chapter_no < expected_ch:
            # This plot thread shouldn't be resolved yet
            keywords = thread.get("payoff_keywords", [])
            for kw in keywords:
                if re.search(kw, text):
                    findings.append({
                        "type": "premature_payoff",
                        "text": f"伏笔'{thread['title']}'提前兑现",
                        "context": f"预期第{expected_ch}章，当前第{chapter_no}章出现'{kw}'",
                        "severity": "high"
                    })
    
    for promise in reader_promises:
        expected_ch = promise.get("expected_chapter", 999)
        if chapter_no < expected_ch:
            keywords = promise.get("payoff_keywords", [])
            for kw in keywords:
                if re.search(kw, text):
                    findings.append({
                        "type": "premature_payoff",
                        "text": f"读者承诺'{promise['title']}'提前兑现",
                        "context": f"预期第{expected_ch}章",
                        "severity": "high"
                    })
    return findings


def run_hallucination_check(text, chapter_no, task_card=None, prev_tail="",
                             prev_brief=None, known_facts=None, plot_threads=None,
                             reader_promises=None, known_states=None, known_relations=None,
                             known_worldbuilding=None):
    """主入口：运行全部幻觉检查，返回报告。"""
    task_card = task_card or {}
    known_facts = known_facts or []
    plot_threads = plot_threads or []
    reader_promises = reader_promises or []
    known_states = known_states or {}
    known_relations = known_relations or {}
    known_worldbuilding = known_worldbuilding or []

    all_findings = []
    blocked = []
    unsupported = []
    contradictions = []

    # 1. Realm shifts
    realm_findings = check_character_realm_shift(text, known_states)
    for f in realm_findings:
        if f["severity"] == "high":
            blocked.append(f)
    all_findings.extend(realm_findings)

    # 2. Relation shifts
    relation_findings = check_relation_shift(text, known_relations)
    for f in relation_findings:
        if f["severity"] == "high":
            blocked.append(f)
    all_findings.extend(relation_findings)

    # 3. New canon
    canon_findings = check_new_canon(text, task_card, known_worldbuilding)
    for f in canon_findings:
        if f["type"] == "unauthorized_canon":
            unsupported.append(f)
        elif f["type"] == "allowed_new_canon":
            pass  # OK
    all_findings.extend(canon_findings)

    # 4. Forgotten state
    state_findings = check_forgotten_state(text, prev_tail, prev_brief)
    all_findings.extend(state_findings)

    # 5. Contradictions
    contra_findings = check_contradictions(text, "", known_facts)
    for f in contra_findings:
        if f["severity"] == "critical":
            contradictions.append(f)
    all_findings.extend(contra_findings)

    # 6. Premature payoff
    payoff_findings = check_premature_payoff(text, chapter_no, plot_threads, reader_promises)
    for f in payoff_findings:
        blocked.append(f)
    all_findings.extend(payoff_findings)

    # Decision
    critical_blockers = [b for b in blocked if b["severity"] in ("high", "critical")]

    # ── Enhanced fields for evidence gate integration ──
    total_hard_claims = len([f for f in all_findings if f.get("severity") in ("high", "critical", "medium")])
    hard_without_source = len(unsupported)
    soft_detail_count = len([f for f in all_findings if f.get("type") == "soft_detail"])
    inferred_count = len([f for f in all_findings if f.get("type") == "inferred_from_known_fact"])

    evidence_coverage = 1.0
    if total_hard_claims > 0:
        evidence_coverage = max(0.0, 1.0 - (hard_without_source / total_hard_claims))

    # evidence_coverage < 0.95 or hard_claims_without_source > 0 => FAIL
    evidence_fail = False
    if evidence_coverage < 0.95:
        evidence_fail = True
    if hard_without_source > 0:
        evidence_fail = True

    status = "FAIL" if (critical_blockers or contradictions or evidence_fail) else "PASS"

    report = {
        "chapter_no": chapter_no,
        "status": status,
        "total_checks": len(all_findings),
        "blocked_items": [{"text": b["text"], "reason": b.get("context","")} for b in blocked],
        "unsupported_claims": [{"text": u["text"], "reason": u.get("context","")} for u in unsupported],
        "contradictions": [{"text": c["text"], "reason": c.get("context","")} for c in contradictions],
        "new_canon_items": [f for f in canon_findings if f["type"] == "allowed_new_canon"],
        "forgotten_state_items": state_findings,
        "final_decision": status,
        "claims_checked": len(all_findings),
        "canon_confirmed_count": len([f for f in canon_findings if f["type"] == "allowed_new_canon"]),
        "allowed_new_canon_count": len([f for f in canon_findings if f["type"] == "allowed_new_canon"]),
        "inferred_claims_count": inferred_count,
        "soft_detail_count": soft_detail_count,
        "evidence_coverage": round(evidence_coverage, 3),
        "hard_claims_without_source": hard_without_source,
        "canon_evidence_map_path": ""
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Hallucination Guard")
    parser.add_argument("chapter_text", help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--task-card", default=None, help="task_card JSON")
    parser.add_argument("--prev-brief", default=None, help="上一章 brief JSON")
    parser.add_argument("--output", default=None, help="输出 report JSON 路径")
    args = parser.parse_args()

    text = Path(args.chapter_text).read_text(encoding="utf-8")
    task_card = {}
    if args.task_card and Path(args.task_card).exists():
        task_card = json.loads(Path(args.task_card).read_text(encoding="utf-8"))

    prev_brief = None
    if args.prev_brief and Path(args.prev_brief).exists():
        prev_brief = json.loads(Path(args.prev_brief).read_text(encoding="utf-8"))

    prev_tail = prev_brief.get("ending_state", "") if prev_brief else ""

    report = run_hallucination_check(
        text, args.chapter_no, task_card=task_card,
        prev_tail=prev_tail, prev_brief=prev_brief
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[OK] report saved: {args.output}")

    if report["status"] == "FAIL":
        print("\n[FAIL] Hallucination detected — chapter blocked")
        sys.exit(1)
    else:
        print("\n[OK] No hallucinations detected")


if __name__ == "__main__":
    main()
