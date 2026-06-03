#!/usr/bin/env python3
"""
continuity_evidence_guard.py — 章章连续证据门禁 v0.3.1-calibrated

硬/软状态分层 + 钩子分层 + 任务钩子信号检测 + 任务误触发排除
"""
import re, json, sys, argparse
from pathlib import Path


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

# ═══════════════════════════════════════════════════
# 硬/软状态分类
# ═══════════════════════════════════════════════════

HARD_INJURY = re.compile(r'(?<!没有)(?<!没)(?<!不)(伤口|流血|骨折|肿|青紫|绷带|包扎|敷药|治疗|养伤|伤势|断臂|残废|濒死|晕倒|眩晕|头晕|昏迷|中毒)')
HARD_TRAPPED = re.compile(r'(被困|锁住|封住|困在|困入|禁锢|无法离开)')
HARD_CRITICAL_ITEM = re.compile(r'(止血丸|玉简|令牌|法器|关键丹药|关键证物|关键书信|证物|残片|密钥|卷轴|禁制符|传送符|信物)')
HARD_CRITICAL_LOCATION = re.compile(r'(时间迟滞区|矿洞深处|阵眼|密室|牢房|战场|危险区域|封印|被困在)')
HARD_LIFE_DEATH = re.compile(r'(?<!没有)(?<!没)(?<!不)(?<!还未)(?<!尚未)(死亡|濒死|追杀|生死危机|处刑|审判|毙命|绝境|垂死|将死)')

SOFT_TASK = re.compile(r'(任务|安排|要求|普通命令)')
SOFT_EMOTION = re.compile(r'(犹豫|沉默|焦虑|愤怒|怀疑|动摇|担忧|失望|愧疚|紧张|兴奋|期待)')
SOFT_LOCATION = re.compile(r'(回到|离开|走进|站在|来到)')
SOFT_BACKGROUND = re.compile(r'(压力|催促|规矩|管事态度|宗门氛围)')
SOFT_PLAN = re.compile(r'(打算|准备|计划|想法)')


def classify_state_markers(text):
    """提取并分类状态标记为 hard/soft"""
    tail = text[-500:]
    result = {
        "hard_states": {},
        "soft_states": {},
    }

    hard = result["hard_states"]
    m = HARD_INJURY.findall(tail)
    if m: hard["injury_state"] = list(set(m))
    m = HARD_TRAPPED.findall(tail)
    if m: hard["trapped_state"] = list(set(m))
    m = HARD_CRITICAL_ITEM.findall(tail)
    if m: hard["critical_item_state"] = list(set(m))
    m = HARD_CRITICAL_LOCATION.findall(tail)
    if m: hard["critical_location_state"] = list(set(m))
    m = HARD_LIFE_DEATH.findall(tail)
    if m: hard["life_death_state"] = list(set(m))

    soft = result["soft_states"]
    m = SOFT_TASK.findall(tail)
    if m: soft["task_state"] = list(set(m))
    m = SOFT_EMOTION.findall(tail)
    if m: soft["emotion_state"] = list(set(m))
    m = SOFT_LOCATION.findall(tail)
    if m: soft["location_state"] = list(set(m))
    m = SOFT_BACKGROUND.findall(tail)
    if m: soft["background_state"] = list(set(m))
    m = SOFT_PLAN.findall(tail)
    if m: soft["plan_state"] = list(set(m))

    return result


def check_state_inheritance(classified_markers, content_start):
    """检查硬状态和软状态的继承情况"""
    start = content_start[:500]
    hard_forgotten = []
    soft_forgotten = []

    for states_dict, target_list in [
        (classified_markers["hard_states"], hard_forgotten),
        (classified_markers["soft_states"], soft_forgotten),
    ]:
        for category, markers_list in states_dict.items():
            for m in markers_list:
                if m not in start:
                    target_list.append({"category": category, "marker": m})

    return hard_forgotten, soft_forgotten


# ═══════════════════════════════════════════════════
# 钩子分层
# ═══════════════════════════════════════════════════

def extract_ending_hooks(tail, end_chars=400):
    """从上一章结尾提取钩子，返回 (hard_hooks, soft_hooks)"""
    text = tail[-end_chars:] if len(tail) > end_chars else tail
    hard = []
    soft = []

    # ── 软钩子：未完成动作（太常见，不强制承接）──
    action_incomplete = re.findall(r'(正要|准备|打算|决定|即将|就要|刚想|刚准备).{0,15}(?:[。！？\n]|$)', text)
    for h in action_incomplete:
        soft.append(("action_incomplete", h.strip()))

    # 不确定性结尾（省略号/问句结尾 → 悬念）
    uncertainty = re.findall(r'[^。！？\n]{10,50}(?:……|\.{3,}|\?|？)\s*$', text, re.MULTILINE)
    for h in uncertainty:
        hard.append(("uncertainty_ending", h.strip()))

    # 新发现/新线索
    discoveries = re.findall(r'(发现|察觉|注意|看出|感觉到|意识到).{0,20}(?:了|到|出)', text)
    for h in discoveries:
        hard.append(("discovery", h.strip()))

    # 人物受伤状态
    injuries = HARD_INJURY.findall(text)
    if injuries:
        hard.append(("character_injury", f"人物状态: {', '.join(set(injuries))}"))

    # 生死危机
    life_death = HARD_LIFE_DEATH.findall(text)
    if life_death:
        hard.append(("life_death", f"生死危机: {', '.join(set(life_death))}"))

    # 被困/禁锢
    trapped = HARD_TRAPPED.findall(text)
    if trapped:
        hard.append(("trapped_state", f"被困状态: {', '.join(set(trapped))}"))

    # 关键物品出现
    critical_items = HARD_CRITICAL_ITEM.findall(text)
    if critical_items:
        hard.append(("critical_item", f"关键物品: {', '.join(set(critical_items))}"))

    # ── 软钩子 ──
    # 普通情绪变化
    emotions = SOFT_EMOTION.findall(text)
    if emotions:
        soft.append(("emotion", f"情绪: {', '.join(set(emotions))}"))

    # 普通计划/打算
    plans = SOFT_PLAN.findall(text)
    if plans:
        soft.append(("plan", f"计划: {', '.join(set(plans))}"))

    # ── 任务钩子：必须通过信号检测 ──
    task_hooks = extract_task_hooks(text)
    hard.extend(task_hooks)

    return hard, soft


# ═══════════════════════════════════════════════════
# 任务钩子信号检测
# ═══════════════════════════════════════════════════

TASK_KEYWORDS = re.compile(r'(任务|安排|吩咐|命令|交代|约定|承诺|限期|必须|要求)')
SIGNAL_EXECUTOR = re.compile(r'(男主|他|她|你|弟子|杂役|众人|管事|师兄|周|林|沈|顾|韩|赵)')
SIGNAL_ACTION = re.compile(r'(去|查|找|送|拿|守|交|还|见|报|采|挖|测|验|带|护|杀|救|完成|处理|搬|清|修|炼)')
SIGNAL_DEADLINE = re.compile(r'(明日|今夜|三日内|之前|天亮前|午时|下次|立刻|马上|今日|今晚|明天|天亮)')
SIGNAL_SOURCE = re.compile(r'(管事|师兄|长老|掌柜|宗门|仙盟|师父|命令|吩咐|交代|执事)')
SIGNAL_CONSEQUENCE = re.compile(r'(否则|不然|违令|罚|死|扣|逐出|问罪|责罚|降等)')

# 任务误触发排除
TASK_FALSE_POSITIVE = re.compile(
    r'(不是任务|不算任务|没有任务|任务已经结束|安排已经废了'
    r'|任务这个词|所谓任务|这个安排|安排得很密|任务感'
    r'|任务像|任务似|安排像|安排似'
    r'|任务完成|安排结束|已经交差|事情已经了结'
    r'|写作任务|系统任务|本章任务|任务卡)'
)


def is_task_false_positive(sentence):
    """检查是否任务误触发"""
    return bool(TASK_FALSE_POSITIVE.search(sentence))


def extract_task_hooks(text):
    """提取真实任务钩子：需要 ≥2 信号"""
    hooks = []
    sentences = re.split(r'[。！？\n]', text)
    for sent in sentences:
        sent = sent.strip()
        if not sent or len(sent) < 10:
            continue
        if not TASK_KEYWORDS.search(sent):
            continue
        if is_task_false_positive(sent):
            continue

        signals = 0
        if SIGNAL_EXECUTOR.search(sent): signals += 1
        if SIGNAL_ACTION.search(sent): signals += 1
        if SIGNAL_DEADLINE.search(sent): signals += 1
        if SIGNAL_SOURCE.search(sent): signals += 1
        if SIGNAL_CONSEQUENCE.search(sent): signals += 1

        if signals >= 2:
            hooks.append(("real_task", sent[:80]))

    return hooks


# ═══════════════════════════════════════════════════
# 钩子承接检查
# ═══════════════════════════════════════════════════

def check_hook_acknowledgment(hooks, content_start):
    """检查钩子承接。hooks 格式: [(type, text), ...]"""
    start = content_start[:600] if len(content_start) > 600 else content_start
    acknowledged = []
    missing = []

    for hook_type, hook_text in hooks:
        keywords = re.findall(r'[\u4e00-\u9fff]{2,4}', hook_text)
        found = any(kw in start for kw in keywords)
        if found:
            acknowledged.append((hook_type, hook_text[:60]))
        else:
            missing.append((hook_type, hook_text[:60]))

    return acknowledged, missing


# ═══════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════

def run_continuity_evidence_check(chapter_no, content, prev_chapter_no=None,
                                   prev_tail="", prev_brief=None,
                                   chapter_plan=None, volume_plan=None):
    """主入口"""

    # 规范化 chapter_no
    chapter_no = safe_int(chapter_no, 0)

    prev_chapter_no = safe_int(prev_chapter_no, 0) or (chapter_no - 1)
    prev_brief = prev_brief or {}
    chapter_plan = chapter_plan or {}
    volume_plan = volume_plan or {}

    content_start = content[:800]

    # ── 第一章特判 ──
    if chapter_no <= 1 or prev_chapter_no < 1:
        return {
            "status": "PASS",
            "final_decision": "PASS",
            "chapter_no": chapter_no,
            "previous_chapter_no": None,
            "previous_tail_used": None,
            "previous_ending_state": "N/A (第一章)",
            "hard_required_hooks": [],
            "soft_required_hooks": [],
            "hard_missing_hooks": [],
            "soft_missing_hooks": [],
            "hard_forgotten_states": [],
            "soft_forgotten_states": [],
            "continuity_conflicts": [],
            "continuity_evidence_score": 1.0,
            "previous_chapter_link_passed": True,
            "warnings": [],
        }

    # ── 上一章结尾 ──
    prev_tail_text = prev_tail or prev_brief.get("ending_state", "")
    previous_tail_used = bool(prev_tail_text)

    # ── 提取钩子（分层）──
    hard_hooks, soft_hooks = extract_ending_hooks(prev_tail_text) if prev_tail_text else ([], [])

    # ── 检查硬钩子承接 ──
    _, hard_missing = check_hook_acknowledgment(hard_hooks, content_start)

    # ── 检查软钩子 ──
    _, soft_missing = check_hook_acknowledgment(soft_hooks, content_start)

    # ── 状态继承（分层）──
    classified = classify_state_markers(prev_tail_text) if prev_tail_text else {"hard_states": {}, "soft_states": {}}
    hard_forgotten, soft_forgotten = check_state_inheritance(classified, content_start)
    # ── 连续性冲突（地点）──
    # 仅当章节开头场景与上一章结尾场景关键词完全不重叠且上一章结尾被困/锁定
    # 时才标记冲突。普通转场（院→林等）不报。
    conflicts = []
    if prev_tail_text and content_start:
        prev_loc = set(re.findall(r'(院|洞|室|殿|阁|楼|厅|堂|巷|街|道|山|林|矿|坊|市|城|镇|村)', prev_tail_text[-200:]))
        curr_loc = set(re.findall(r'(院|洞|室|殿|阁|楼|厅|堂|巷|街|道|山|林|矿|坊|市|城|镇|村)', content_start[:200]))
        prev_trapped = HARD_TRAPPED.search(prev_tail_text[-200:])
        if prev_loc and curr_loc and not (prev_loc & curr_loc) and prev_trapped:
            conflicts.append(f"被困状态下地点跳转: 上章={list(prev_loc)}, 本章={list(curr_loc)}")

    # ── 裁决 ──
    hard_missing_count = len(hard_missing)
    hard_forgotten_count = len(hard_forgotten)
    soft_forgotten_count = len(soft_forgotten)
    conflict_count = len(conflicts)

    # 硬状态：零容忍
    hard_state_pass = (hard_forgotten_count == 0)

    # 软状态：允许少量
    total_soft = sum(len(v) for v in classified["soft_states"].values())
    max_soft_forgiven = max(2, total_soft // 3) if total_soft > 0 else 0
    soft_state_pass = (soft_forgotten_count <= max_soft_forgiven)

    # 钩子：硬钩子零容忍
    hooks_pass = (hard_missing_count == 0)

    # 连续性冲突
    conflicts_pass = (conflict_count == 0)

    # 综合得分
    total_hard = len(hard_hooks)
    hook_score = 1.0 if total_hard == 0 else (total_hard - hard_missing_count) / total_hard
    total_hard_markers = sum(len(v) for v in classified["hard_states"].values())
    hard_state_score = 1.0 if total_hard_markers == 0 else (total_hard_markers - hard_forgotten_count) / total_hard_markers
    evidence_score = round(hook_score * 0.5 + hard_state_score * 0.3 + (1.0 if conflicts_pass else 0.5) * 0.2, 2)

    previous_chapter_link_passed = (
        previous_tail_used and
        hooks_pass and
        hard_state_pass and
        conflicts_pass and
        evidence_score >= 0.65
    )

    final_decision = "PASS" if previous_chapter_link_passed else "FAIL"

    # ── Warnings ──
    warnings = []
    if not soft_state_pass:
        warnings.append(f"软状态遗忘 {soft_forgotten_count} 项（允许 ≤{max_soft_forgiven}）")
    if soft_missing:
        warnings.append(f"软钩子未承接: {len(soft_missing)} 项")
    if evidence_score < 0.8:
        warnings.append(f"连续性得分偏低 ({evidence_score})")

    # ── 构建报告 ──
    hard_missing_str = [f"{t}:{h}" for t, h in hard_missing]
    soft_missing_str = [f"{t}:{h}" for t, h in soft_missing]
    hard_forgotten_str = [f"{f['category']}:{f['marker']}" for f in hard_forgotten]
    soft_forgotten_str = [f"{f['category']}:{f['marker']}" for f in soft_forgotten]
    hard_hooks_str = [f"{t}:{h[:60]}" for t, h in hard_hooks]

    report = {
        "status": final_decision,
        "final_decision": final_decision,
        "chapter_no": chapter_no,
        "previous_chapter_no": prev_chapter_no,
        "previous_tail_used": previous_tail_used,
        "previous_ending_state": prev_tail_text[:200] if prev_tail_text else "",
        "hard_required_hooks": hard_hooks_str[:10],
        "soft_required_hooks": [f"{t}:{h[:60]}" for t, h in soft_hooks][:10],
        "hard_missing_hooks": hard_missing_str,
        "soft_missing_hooks": soft_missing_str,
        "hard_forgotten_states": hard_forgotten_str,
        "soft_forgotten_states": soft_forgotten_str,
        "hard_forgotten_states_count": hard_forgotten_count,
        "soft_forgotten_states_count": soft_forgotten_count,
        "continuity_conflicts": conflicts,
        "continuity_evidence_score": evidence_score,
        "previous_chapter_link_passed": previous_chapter_link_passed,
        "warnings": warnings,
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Continuity Evidence Guard")
    parser.add_argument("--chapter-no", type=int, required=True, help="章节号")
    parser.add_argument("--content-file", required=True, help="章节 TXT 文件")
    parser.add_argument("--prev-chapter-no", type=int, default=None)
    parser.add_argument("--prev-brief", default=None, help="上一章 brief JSON")
    parser.add_argument("--chapter-plan", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    content = Path(args.content_file).read_text(encoding="utf-8")

    prev_tail = ""
    prev_brief = None
    if args.prev_brief and Path(args.prev_brief).exists():
        prev_brief = json.loads(Path(args.prev_brief).read_text(encoding="utf-8"))
        prev_tail = prev_brief.get("ending_state", "")

    chapter_plan = {}
    if args.chapter_plan and Path(args.chapter_plan).exists():
        chapter_plan = json.loads(Path(args.chapter_plan).read_text(encoding="utf-8"))

    report = run_continuity_evidence_check(
        args.chapter_no, content,
        prev_chapter_no=args.prev_chapter_no,
        prev_tail=prev_tail,
        prev_brief=prev_brief,
        chapter_plan=chapter_plan
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[OK] report saved: {args.output}")

    if report["final_decision"] == "FAIL":
        print(f"\n[FAIL] Continuity evidence check failed")
        print(f"  hard_missing_hooks: {len(report['hard_missing_hooks'])}")
        print(f"  hard_forgotten_states: {len(report['hard_forgotten_states'])}")
        print(f"  score: {report['continuity_evidence_score']}")
        sys.exit(1)
    else:
        print(f"\n[OK] Continuity evidence check passed (score: {report['continuity_evidence_score']})")


if __name__ == "__main__":
    main()
