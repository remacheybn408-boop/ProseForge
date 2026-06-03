#!/usr/bin/env python3
"""
scene_causality_guard.py — 场景因果链门禁 v0.4.0

检查场景的 CARCRH 因果链完整性：
  Cause → Action → Resistance → Cost → Result → Hook

按对话群或段落组分场景，每个重要场景至少需要 4/6 个因果链元素。
只做 WARNING，不硬拦。

用法:
  python scripts/scene_causality_guard.py \
    --input chapter.txt --chapter-no 1 [--output report.json]
"""
import re, json, sys, argparse
from pathlib import Path
from typing import List, Dict, Tuple
from consequence_lexicon import (
    find_all_consequences,
    count_visible_consequences,
    has_minimum_visible_cost,
)


# ═══════════════════════════════════════════════════
# 因果链检测词库
# ═══════════════════════════════════════════════════

# 原因标记：因为/由于/为了/想到
CAUSE_PATTERNS = re.compile(
    r'(因为|由于|为了|想到|想起|意识到|发觉|发现|觉察|察觉'
    r'|看出|感到|觉得|认为|以为|明白|知道|懂[得了]|悟[到了出]'
    r'|原来|其实|本来|原本|当初|此前|此前|日前|不久前|不久前'
    r'|因[为]|出于|鉴于|基于|源于|起于|始于|动机|目的|理由)'
)

# 行动标记：动手/试/测/做/行/走/去
ACTION_PATTERNS = re.compile(
    r'(动手|下手|着手|出手|做[了过到起完]|试[了过探一试]|测[了试过]'
    r'|行[动走了起来]|走[了过去进出开来回]|去[了做过到]'
    r'|干[了完起来掉]|弄[了完好起来]|搞[了定清楚明白]'
    r'|施[展了放法术]|运[转行用了]|催[动了发]|引[发了动]'
    r'|发[动了出起]|启[动了]|开[始了启]|动手|行动|操作|执行)'
)

# 阻力标记：但/然而/可是/却/不料/结果
RESISTANCE_PATTERNS = re.compile(
    r'(但[是]?|然而|可是|不过|却[不料]?|不料|谁知|哪[知料到]'
    r'|居然|竟然|偏偏|反而|反倒|反倒|反|则不然|反而|反倒'
    r'|不料|没想到|没成想|结果|到头来|最终|最后'
    r'|阻力|阻碍|障碍|困难|麻烦|问题|意外|变故|变数'
    r'|打断|阻止|阻挠|拦截|干扰|搅乱|破坏|打乱|扰乱|搅局)'
)

# 代价标记：付出/牺牲/失去/裂/碎/破/消耗/代价
COST_PATTERNS = re.compile(
    r'(付出|牺牲|失去|损失|丧失|耗尽|消耗|花费|费[了尽去]|浪费'
    r'|裂[开了缝碎]|碎[了裂开]|破[了裂碎开坏相口洞]|断[了裂开]'
    r'|伤[了到害口势]|流血|受伤|负伤|重伤|轻伤|创[伤口]'
    r'|代价|后果|损失|损耗|亏[了空损]|赔[了上进去]'
    r'|体力|灵力|法力|功力|修为|精力|心力|气血|元气'
    r'|疲倦|疲惫|力竭|虚脱|透支|油尽灯枯'
    r'|来不及|晚了|错过|延误|耽搁|耽误'
    r'|残缺|破损|毁坏|报废|作废|失效|失灵|故障)'
)

# 结果标记：于是/所以/终于/最后/结果
RESULT_PATTERNS = re.compile(
    r'(于是|所以|因此|因而|终于|最后|最终|终于|总算|到底|到头来'
    r'|结果|结论|结局|后果|善后|收场|告终|落下帷幕'
    r'|成功了|失败[了]|达成[了]|完成[了]|实现[了]|做到[了]'
    r'|落空|泡汤|白费|前功尽弃|付之东流|化为乌有'
    r'|得[到了出偿]|获[取得了]|赢[得了]|输[了掉]|败[了退]'
    r'|尘埃落定|大功告成|功成[了]|事成|成了|妥了|定了)'
)

# 钩子标记：但/然而/留下/新的/异常
HOOK_PATTERNS = re.compile(
    r'(但[是]?|然而|可是|不过|却|不料|谁知|哪[知料到]'
    r'|留下[了]|剩下|余下|残[留余存]|遗留|残留'
    r'|新的|新增|突然|忽然|猛地|骤然|蓦地|猝然|兀[自地]'
    r'|异常|奇怪|古怪|诡异|不对劲|不对|不妥|异样|异状|异象|异动'
    r'|未[解了完]|悬[而未决着]|疑[点问团案惑]|谜[题团]|端倪|蛛丝马迹'
    r'|暗示|预示|预兆|征兆|兆头|迹象|踪迹|线索|伏笔|铺垫'
    r'|未完待续|下回|后续|后话|且听|欲知)'
)


# ═══════════════════════════════════════════════════
# 场景分割
# ═══════════════════════════════════════════════════

def split_into_scenes(text: str) -> List[Dict]:
    """
    将文本按场景分割。
    规则：按段落分组，遇到长段落转折或对话群边界时切分。
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return []

    scenes = []
    current_scene = []
    scene_idx = 0

    for i, para in enumerate(paragraphs):
        current_scene.append(para)

        # 场景切分条件：
        # 1. 段落以明显的时间/地点转换开头
        # 2. 已累积足够内容（>=3段）
        # 3. 遇到空行分隔
        time_shift = bool(re.match(r'^(第[二三四五六七八九十]|翌|次|数|几|半|[一三]个|那天|当晚)', para))
        place_shift = bool(re.match(r'^(而|另一|这边|那边|此[时地处]|镜头)', para))

        should_cut = False
        if len(current_scene) >= 3 and (time_shift or place_shift):
            should_cut = True
        elif len(current_scene) >= 6:
            # 段落数多了也该切
            should_cut = True

        if i == len(paragraphs) - 1:
            should_cut = True  # 最后一段必须切

        if should_cut:
            scene_text = "\n".join(current_scene)
            if len(scene_text.strip()) >= 30:
                scene_idx += 1
                scenes.append({
                    "index": scene_idx,
                    "text": scene_text,
                })
            current_scene = []

    # 处理剩余
    if current_scene:
        scene_text = "\n".join(current_scene)
        if len(scene_text.strip()) >= 30:
            scene_idx += 1
            scenes.append({
                "index": scene_idx,
                "text": scene_text,
            })

    return scenes


# ═══════════════════════════════════════════════════
# 因果链元素检测
# ═══════════════════════════════════════════════════

def detect_cause(text: str) -> bool:
    """检测是否有原因标记"""
    return bool(CAUSE_PATTERNS.search(text))


def detect_action(text: str) -> bool:
    """检测是否有行动标记"""
    return bool(ACTION_PATTERNS.search(text))


def detect_resistance(text: str) -> bool:
    """检测是否有阻力标记"""
    return bool(RESISTANCE_PATTERNS.search(text))


def detect_cost(text: str) -> bool:
    """检测是否有代价标记"""
    return bool(COST_PATTERNS.search(text))


def detect_result(text: str) -> bool:
    """检测是否有结果标记"""
    return bool(RESULT_PATTERNS.search(text))


def detect_hook(text: str) -> bool:
    """检测是否有钩子标记"""
    return bool(HOOK_PATTERNS.search(text))


# ═══════════════════════════════════════════════════
# 场景分析
# ═══════════════════════════════════════════════════

ELEMENT_DETECTORS = {
    "cause": detect_cause,
    "action": detect_action,
    "resistance": detect_resistance,
    "cost": detect_cost,
    "result": detect_result,
    "hook": detect_hook,
}

ELEMENT_LABELS = {
    "cause": "原因(Cause)",
    "action": "行动(Action)",
    "resistance": "阻力(Resistance)",
    "cost": "代价(Cost)",
    "result": "结果(Result)",
    "hook": "钩子(Hook)",
}


def analyze_scene(scene: Dict) -> Dict:
    """分析单个场景的因果链元素"""
    text = scene["text"]
    elements_found = {}
    for elem_name, detector in ELEMENT_DETECTORS.items():
        elements_found[elem_name] = detector(text)

    total = sum(1 for v in elements_found.values() if v)

    return {
        "scene_index": scene["index"],
        "elements": elements_found,
        "total_elements": total,
        "carchh_score": total / 6,
        "sample": text[:80],
    }


def analyze_scenes(scenes: List[Dict], min_detailed: int = 3) -> Dict:
    """
    分析所有场景的因果链覆盖。
    只对较长场景（>=3段）要求因果链。
    """
    if not scenes:
        return {
            "scene_count": 0,
            "scenes_with_cause": 0,
            "scenes_with_action": 0,
            "scenes_with_resistance": 0,
            "scenes_with_cost": 0,
            "scenes_with_result": 0,
            "scenes_with_hook": 0,
            "scenes_meeting_threshold": 0,
            "causality_coverage": 1.0,
            "weak_scenes": [],
            "per_scene": [],
        }

    scene_results = []
    for scene in scenes:
        result = analyze_scene(scene)
        scene_results.append(result)

    # 汇总统计
    total = len(scenes)
    count_cause = sum(1 for r in scene_results if r["elements"]["cause"])
    count_action = sum(1 for r in scene_results if r["elements"]["action"])
    count_resistance = sum(1 for r in scene_results if r["elements"]["resistance"])
    count_cost = sum(1 for r in scene_results if r["elements"]["cost"])
    count_result = sum(1 for r in scene_results if r["elements"]["result"])
    count_hook = sum(1 for r in scene_results if r["elements"]["hook"])

    # 达到阈值的场景（>=4个元素）
    threshold = 4
    meeting = sum(1 for r in scene_results if r["total_elements"] >= threshold)

    # 因果链覆盖度
    coverage = meeting / total if total > 0 else 1.0

    # 弱场景（<4 个元素）
    weak = [
        {
            "scene_index": r["scene_index"],
            "total_elements": r["total_elements"],
            "missing": [
                ELEMENT_LABELS[k] for k, v in r["elements"].items() if not v
            ],
            "sample": r["sample"],
        }
        for r in scene_results if r["total_elements"] < threshold
    ]

    return {
        "scene_count": total,
        "scenes_with_cause": count_cause,
        "scenes_with_action": count_action,
        "scenes_with_resistance": count_resistance,
        "scenes_with_cost": count_cost,
        "scenes_with_result": count_result,
        "scenes_with_hook": count_hook,
        "scenes_meeting_threshold": meeting,
        "causality_coverage": round(coverage, 3),
        "weak_scenes": weak,
        "per_scene": scene_results,
    }


# ═══════════════════════════════════════════════════
# 主检查函数
# ═══════════════════════════════════════════════════

def run_scene_causality_check(content: str, chapter_no: int) -> dict:
    """执行场景因果链门禁检查，返回报告 dict"""

    scenes = split_into_scenes(content)
    analysis = analyze_scenes(scenes)

    # ── 构建 flags 和 suggestions ──
    flags = []
    suggestions = []

    if analysis["scene_count"] == 0:
        return {
            "guard": "scene_causality_guard",
            "version": "v0.4.0",
            "status": "PASS",
            "scene_count": 0,
            "scenes_with_cause": 0,
            "scenes_with_cost": 0,
            "scenes_with_result": 0,
            "causality_coverage": 1.0,
            "flags": [],
            "suggestions": [],
            "hard_fail": False,
        }

    # 因果链覆盖率低
    if analysis["causality_coverage"] < 0.5:
        flags.append({
            "level": "WARNING",
            "type": "LOW_CAUSALITY_COVERAGE",
            "message": (
                f"场景因果链覆盖率 {analysis['causality_coverage']:.0%}，"
                f"仅 {analysis['scenes_meeting_threshold']}/{analysis['scene_count']} "
                f"个场景满足 CARCRH（≥4元素）。"
            )
        })
        suggestions.append(
            "加强场景因果链：确保每个重要场景有 Cause→Action→Resistance→Cost→Result→Hook。"
        )

    # Cost 缺失普遍 — 先用 lexicon 检查叙事化代价
    lexicon_passed, lexicon_count, lexicon_details = has_minimum_visible_cost(content, min_cost=2)
    legacy_cost_hit = analysis["scenes_with_cost"] >= max(1, analysis["scene_count"] * 0.4)
    cost_sufficient = legacy_cost_hit or lexicon_passed

    if not cost_sufficient:
        flags.append({
            "level": "WARNING",
            "type": "MISSING_COST_ELEMENT",
            "message": (
                f"代价(Cost)元素缺失严重，仅 {analysis['scenes_with_cost']}"
                f"/{analysis['scene_count']} 场景包含传统代价关键词，"
                f"且叙事化可见代价仅 {lexicon_count} 处。"
            )
        })
        suggestions.append(
            "让角色的行动产生代价——受伤、消耗、牺牲、损坏物品、失去机会等。"
        )

    # Cause 缺失
    if analysis["scenes_with_cause"] < max(1, analysis["scene_count"] * 0.4):
        flags.append({
            "level": "WARNING",
            "type": "MISSING_CAUSE_ELEMENT",
            "message": (
                f"原因(Cause)元素缺失，仅 {analysis['scenes_with_cause']}"
                f"/{analysis['scene_count']} 场景有明确动机/原因。"
            )
        })
        suggestions.append(
            "为角色的每个行动提供动机——'因为…所以…'的逻辑链要读者能追踪。"
        )

    # Result 缺失
    if analysis["scenes_with_result"] < max(1, analysis["scene_count"] * 0.3):
        flags.append({
            "level": "WARNING",
            "type": "MISSING_RESULT_ELEMENT",
            "message": (
                f"结果(Result)元素缺失，仅 {analysis['scenes_with_result']}"
                f"/{analysis['scene_count']} 场景有明确结局/结果。"
            )
        })
        suggestions.append(
            "每场戏都要有结果——成功/失败/半途而废/意外收获，不能'就那样'结束。"
        )

    # Hook 缺失
    if analysis["scenes_with_hook"] < max(1, analysis["scene_count"] * 0.3):
        flags.append({
            "level": "WARNING",
            "type": "MISSING_HOOK_ELEMENT",
            "message": (
                f"钩子(Hook)元素缺失，仅 {analysis['scenes_with_hook']}"
                f"/{analysis['scene_count']} 场景留下悬念/异常。"
            )
        })
        suggestions.append(
            "每场戏结尾留'钩子'——异常细节、未解疑问、下一危机的暗示，驱动翻页欲。"
        )

    # ── 判定状态 ──
    status = "WARNING" if flags else "PASS"

    report = {
        "guard": "scene_causality_guard",
        "version": "v0.4.5",
        "status": status,
        "scene_count": analysis["scene_count"],
        "scenes_with_cause": analysis["scenes_with_cause"],
        "scenes_with_cost": analysis["scenes_with_cost"],
        "scenes_with_result": analysis["scenes_with_result"],
        "scenes_meeting_threshold": analysis["scenes_meeting_threshold"],
        "causality_coverage": analysis["causality_coverage"],
        "metrics": {
            "legacy_cost_hits": analysis["scenes_with_cost"],
            "visible_consequence_count": lexicon_count,
            "physical_count": lexicon_details["physical_count"],
            "object_count": lexicon_details["object_count"],
            "social_count": lexicon_details["social_count"],
            "rule_count": lexicon_details["rule_count"],
        },
        "flags": flags,
        "suggestions": suggestions,
        "hard_fail": False,
    }

    return report


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Scene Causality Guard — 场景因果链门禁"
    )
    parser.add_argument("--input", required=True, help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--output", default=None, help="输出 report JSON 文件")
    args = parser.parse_args()

    content = Path(args.input).read_text(encoding="utf-8")
    report = run_scene_causality_check(content, args.chapter_no)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n[OK] Scene causality report saved: {args.output}")

    if report["status"] == "WARNING":
        print(f"\n[WARN] Scene causality: {len(report['flags'])} flags, "
              f"{len(report['suggestions'])} suggestions")
    else:
        print(f"\n[OK] Scene causality passed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
