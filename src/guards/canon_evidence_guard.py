#!/usr/bin/env python3
"""
canon_evidence_guard.py — 防幻觉来源证据门禁

每个新增硬事实必须绑定来源。不是"感觉乱编"，而是 hard_claim 没有 evidence source。

硬事实类型: character_identity, character_realm, relationship, faction,
  cultivation_method, world_rule, timeline, major_item, plot_payoff,
  reader_promise_payoff, injury_state, location_state, volume_bridge_state

来源类型: previous_tail, recent_summaries, chapter_task_card, chapter_plan,
  volume_plan, volume_bridge_report, character_state, location_state,
  worldbuilding, plot_thread, reader_promise, timeline_event,
  user_instruction, allowed_new_canon, inferred_from_known_fact,
  soft_detail, none

用法:
  python scripts/canon_evidence_guard.py content.txt \
    --chapter-no 5 [--task-card tc.json] [--output report.json] \
    [--evidence-map evidence.json]
"""

import re, json, sys, argparse
from pathlib import Path


# ── 硬事实提取模式 ──
HARD_CLAIM_PATTERNS = {
    "character_identity": [
        r'(原来是|其实是|真正的身份是|真实身份是).{0,5}(的)?(人|者|弟子|师兄|师姐|师弟|师妹|师父|父亲|母亲|儿子|女儿|兄弟|姐妹|仇人|恩人|凶手|幕后|卧底|内奸|叛徒)',
        r'(并非.{1,5}而是).{0,5}(的)?(人|者|弟子|师兄|师姐|师弟|师妹|师父|父亲|母亲|儿子|女儿|兄弟|姐妹|仇人|恩人|凶手|幕后|卧底|内奸|叛徒)',
    ],
    "character_realm": [
        r'(突破.{0,2}(筑基|金丹|元婴|化神|炼虚|合体|大乘|渡劫|练气|引气))',
        r'(晋升.{0,2}(筑基|金丹|元婴|化神|炼虚|合体|大乘|渡劫))',
        r'(踏入.{0,2}(筑基|金丹|元婴|化神|炼虚|合体|大乘|渡劫))',
    ],
    "relationship": [
        r'(原来|其实|竟然是).{0,5}(的)(师父|弟子|师兄|师姐|师弟|师妹|父亲|母亲|儿子|女儿|兄弟|姐妹|仇人|恩人)',
        r'(背叛|出卖|反水|决裂|结盟|联手)',
    ],
    "faction": [
        r'(宗门|教派|组织|势力|帮派|世家|仙盟|魔教).{0,10}(出现|现身|崛起|成立|创立)',
        r'(从未听过|从未见过|闻所未闻)的(宗门|教派|势力|组织)',
    ],
    "cultivation_method": [
        r'(领悟|掌握|觉醒|获得|创出|发明).{0,15}(功法|能力|力量|神通|秘术|手段|技术)',
        r'(新的|前所未有|独创).{0,10}(修炼|功法|秘术|方法|体系)',
    ],
    "world_rule": [
        r'(原来|其实|事实上).{0,10}(规则|法则|定律|规律|天道).{0,15}(是|在于|就是)',
        r'(并非.{0,10}而是).{0,20}',
    ],
    "timeline": [
        r'(\d+年[前后]|\d+万年前|\d+千年前|\d+百年前)',
    ],
    "major_item": [
        r'(获得|得到|拿到|捡到|发现).{0,15}(宝物|神器|法宝|灵器|仙器|圣物|秘宝)',
    ],
    "plot_payoff": [
        r'(终于|总算|到底).{0,5}(恢复|找回|发现|突破|击败|打倒|解决)',
    ],
    "reader_promise_payoff": [
        r'(终于|总算|到底).{0,5}(揭晓|揭开|公布|公开|露出|展现)',
    ],
    "injury_state": [
        r'(受伤|伤口|流血|骨折|中毒|晕倒|昏迷)',
        r'(治愈|痊愈|恢复|好转).{0,10}(伤势|伤口|伤)',
    ],
    "location_state": [
        r'(来到|到达|抵达|进入).{0,15}(新的|未知的|从未去过)',
    ],
}


def extract_claims(text):
    """从正文提取所有硬事实声明"""
    claims = []
    for claim_type, patterns in HARD_CLAIM_PATTERNS.items():
        for pattern in patterns:
            for m in re.finditer(pattern, text):
                context_start = max(0, m.start() - 30)
                context_end = min(len(text), m.end() + 30)
                claims.append({
                    "claim": m.group(),
                    "claim_type": claim_type,
                    "context": text[context_start:context_end],
                    "position": m.start(),
                    "source_type": "none",  # to be filled
                    "source_ref": "",
                    "status": "unbound",
                    "allowed": None
                })
    return claims


def bind_sources(claims, task_card=None, prev_tail="", prev_brief=None,
                 known_facts=None, worldbuilding=None):
    """为每个硬事实绑定来源"""
    task_card = task_card or {}
    known_facts = known_facts or []
    worldbuilding = worldbuilding or []

    for claim in claims:
        claim_text = claim["claim"]
        claim_type = claim["claim_type"]

        # 1. 来自 task_card
        allowed_canon = task_card.get("allowed_new_canon", [])
        must_include = task_card.get("must_include", "")
        if any(ac in claim_text for ac in allowed_canon):
            claim["source_type"] = "chapter_task_card"
            claim["source_ref"] = f"task_card.allowed_new_canon"
            claim["status"] = "allowed_new_canon"
            claim["allowed"] = True
            continue
        if must_include and any(kw in claim_text for kw in re.findall(r'[\u4e00-\u9fff]{3,6}', must_include)):
            claim["source_type"] = "chapter_task_card"
            claim["source_ref"] = "task_card.must_include"
            claim["status"] = "allowed_new_canon"
            claim["allowed"] = True
            continue

        # 2. 来自上一章
        if prev_tail and any(kw in prev_tail[-400:] for kw in re.findall(r'[\u4e00-\u9fff]{3,6}', claim_text)):
            claim["source_type"] = "previous_tail"
            claim["source_ref"] = "previous_tail"
            claim["status"] = "canon_confirmed"
            claim["allowed"] = True
            continue

        # 3. 来自 prev_brief
        if prev_brief:
            brief_text = json.dumps(prev_brief, ensure_ascii=False)
            if any(kw in brief_text for kw in re.findall(r'[\u4e00-\u9fff]{3,6}', claim_text)):
                claim["source_type"] = "previous_tail"
                claim["source_ref"] = "prev_brief"
                claim["status"] = "canon_confirmed"
                claim["allowed"] = True
                continue

        # 4. 来自已知世界观
        for wb in worldbuilding:
            wb_title = wb.get("title", "") if isinstance(wb, dict) else str(wb)
            if any(kw in wb_title for kw in re.findall(r'[\u4e00-\u9fff]{3,6}', claim_text)):
                claim["source_type"] = "worldbuilding"
                claim["source_ref"] = f"worldbuilding:{wb_title[:40]}"
                claim["status"] = "canon_confirmed"
                claim["allowed"] = True
                break
        if claim["source_type"] != "none":
            continue

        # 5. 软细节（不改变 canon 的描述性文字）
        if claim_type in ("injury_state", "location_state"):
            # 这些可能是正常的叙事推进
            claim["source_type"] = "soft_detail"
            claim["source_ref"] = "narrative_progression"
            claim["status"] = "soft_detail"
            claim["allowed"] = True
            continue

        # 6. 仍无来源 — 可能的幻觉
        claim["source_type"] = "none"
        claim["source_ref"] = ""
        claim["status"] = "unsupported_hallucination"
        claim["allowed"] = False

    return claims


def run_canon_evidence_check(content, chapter_no, task_card=None,
                              prev_tail="", prev_brief=None,
                              known_facts=None, worldbuilding=None):
    """主入口：运行来源证据检查"""

    # 提取声明
    claims = extract_claims(content)

    # 绑定来源
    claims = bind_sources(claims,
        task_card=task_card,
        prev_tail=prev_tail,
        prev_brief=prev_brief,
        known_facts=known_facts,
        worldbuilding=worldbuilding)

    # ── 统计分析 ──
    canon_confirmed = [c for c in claims if c["status"] == "canon_confirmed"]
    allowed_new = [c for c in claims if c["status"] == "allowed_new_canon"]
    inferred = [c for c in claims if c["status"] == "inferred_from_known_fact"]
    soft_details = [c for c in claims if c["status"] == "soft_detail"]
    unsupported = [c for c in claims if c["status"] == "unsupported_hallucination"]
    # contradictions would be checked by hallucination_guard

    total_hard = len(canon_confirmed) + len(allowed_new) + len(inferred) + len(unsupported)
    total_all = len(claims)

    if total_hard > 0:
        evidence_coverage = round(1.0 - (len(unsupported) / total_hard), 3)
    else:
        evidence_coverage = 1.0  # no hard claims = nothing to check

    # ── 裁决 ──
    hard_without_source = len(unsupported)
    failed = hard_without_source > 0 or evidence_coverage < 0.95
    status = "FAIL" if failed else "PASS"

    report = {
        "chapter_no": chapter_no,
        "status": status,
        "final_decision": status,
        "claims_checked": total_all,
        "canon_confirmed_count": len(canon_confirmed),
        "allowed_new_canon_count": len(allowed_new),
        "inferred_claims_count": len(inferred),
        "soft_detail_count": len(soft_details),
        "unsupported_claims": [{"claim": c["claim"], "context": c["context"][:80]} for c in unsupported],
        "contradictions": [],
        "blocked_items": [],
        "canon_evidence_map_path": "",
        "evidence_coverage": evidence_coverage,
        "hard_claims_without_source": hard_without_source
    }

    return report, claims


def main():
    parser = argparse.ArgumentParser(description="Canon Evidence Guard")
    parser.add_argument("content_file", help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--task-card", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--evidence-map", default=None, help="输出 canon_evidence_map JSON")
    args = parser.parse_args()

    content = Path(args.content_file).read_text(encoding="utf-8")

    task_card = {}
    if args.task_card and Path(args.task_card).exists():
        task_card = json.loads(Path(args.task_card).read_text(encoding="utf-8"))

    report, claims = run_canon_evidence_check(content, args.chapter_no, task_card=task_card)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[OK] report saved: {args.output}")

    if args.evidence_map:
        Path(args.evidence_map).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_map).write_text(json.dumps(claims, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] evidence_map saved: {args.evidence_map}")

    if report["status"] == "FAIL":
        print(f"\n[FAIL] Canon evidence check failed")
        print(f"  hard_claims_without_source: {report['hard_claims_without_source']}")
        print(f"  evidence_coverage: {report['evidence_coverage']}")
        sys.exit(1)
    else:
        print(f"\n[OK] Canon evidence check passed (coverage: {report['evidence_coverage']})")


if __name__ == "__main__":
    main()
