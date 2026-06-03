#!/usr/bin/env python3
"""
dialogue_beat_guard.py — 对白节拍门禁 v0.3.1-qgp

检查重要场景的对白中是否有：
1. 具体动作 (action_beat)
2. 停顿或沉默 (pause_beat)
3. 误会或错误判断 (misunderstanding_beat)
4. 代价或损失 (cost_beat)

每个重要场景至少满足 2 项。

策略: Phase 2 — 先 WARNING，不 FAIL
"""
import re, json, sys, argparse
from pathlib import Path

# ═══════════════════════════════════════════════════
# 节拍检测
# ═══════════════════════════════════════════════════

ACTION_BEAT = re.compile(
    r'(抬手|放下|拿起|放下|推开|拉开门|转身|回头|蹲下|站起|坐下|走过去|退后|往前|往后退)'
    r'|(攥|握|捏|掐|按|推|拉|扯|拽|甩|扔|丢|砸|砍|刺|劈|划|点|指|敲|拍|磕|抹|擦)'
    r'|(拔出|收剑|拔剑|抽刀|掏|取出|放回|塞进|揣|揣进|揣入)'
)

PAUSE_BEAT = re.compile(
    r'(沉默|停顿|不语|没有回答|没说话|没有回应|静默|安静下来)'
    r'|(停.{0,5}(了|下|住|顿|片刻|半晌))'
    r'|(……|\\.{3,})'
    r'|(深吸一口气|呼出一口气|闭上眼|睁开眼)'
)

MISUNDERSTANDING_BEAT = re.compile(
    r'(以为|误会|误解|错以为|错认|误认|看错|听错|会错意)'
    r'|(不是你想象|不是你想的|你搞错了|你错了|不对.{0,5}不是)'
    r'|(原来不是|竟然不是|居然不是|其实不是)'
    r'|(脸色一下变了|猛地反应过来|突然意识到自己)'
)

COST_BEAT = re.compile(
    r'(付出|失去|损失|消耗|烧掉|耗光|用光了|花光了|丢|没了|消失了)'
    r'|(代价|后果|报应|反噬|副作用|后遗症)'
    r'|(耳鸣|头晕|嘴角渗血|咳血|伤口裂开|旧伤复发|脱力|虚脱)'
    r'|(再也.{0,5}(不|没|无法|不能))'
    r'|(裂|碎|断|破|残|废|毁).{0,5}(了|的)'
)


def split_scenes_by_dialogue(content):
    """按对白群拆分场景"""
    paragraphs = content.split('\n')
    scenes = []
    current = []
    in_dialogue = False

    for p in paragraphs:
        p = p.strip()
        if not p:
            if current:
                scenes.append('\n'.join(current))
                current = []
            in_dialogue = False
            continue

        has_dialogue = bool(re.search(r'[""「」]', p))
        if has_dialogue:
            current.append(p)
            in_dialogue = True
        elif in_dialogue:
            current.append(p)
        else:
            if current:
                scenes.append('\n'.join(current))
                current = []
            in_dialogue = False

    if current:
        scenes.append('\n'.join(current))

    return [s for s in scenes if s.strip()]


def analyze_scene_beats(scene_text):
    """分析单场景的节拍"""
    return {
        "action_beat_count": len(ACTION_BEAT.findall(scene_text)),
        "pause_beat_count": len(PAUSE_BEAT.findall(scene_text)),
        "misunderstanding_present": bool(MISUNDERSTANDING_BEAT.search(scene_text)),
        "cost_present": bool(COST_BEAT.search(scene_text)),
    }


def run_dialogue_beat_check(content, chapter_no):
    """主入口"""
    scenes = split_scenes_by_dialogue(content)

    if not scenes:
        return {
            "status": "PASS",
            "final_decision": "PASS",
            "chapter_no": chapter_no,
            "scenes_analyzed": 0,
            "scene_reports": [],
            "scenes_passing": 0,
            "scenes_failing": 0,
            "dialogue_beat_pass": True,
            "violations": [],
            "warnings": [],
        }

    scene_reports = []
    passing = 0
    failing = 0
    violations = []
    warnings = []

    for i, scene in enumerate(scenes):
        beats = analyze_scene_beats(scene)

        # 每场景至少满足 2 项
        conditions_met = sum([
            beats["action_beat_count"] > 0,
            beats["pause_beat_count"] > 0,
            beats["misunderstanding_present"],
            beats["cost_present"],
        ])

        scene_report = {
            "scene_id": f"chapter_{chapter_no:03d}_scene_{i+1:02d}",
            "action_beat_count": beats["action_beat_count"],
            "pause_beat_count": beats["pause_beat_count"],
            "misunderstanding_present": beats["misunderstanding_present"],
            "cost_present": beats["cost_present"],
            "conditions_met": conditions_met,
            "dialogue_beat_pass": conditions_met >= 2,
        }
        scene_reports.append(scene_report)

        if conditions_met >= 2:
            passing += 1
        else:
            failing += 1
            warnings.append(
                f"场景 {i+1}: 只满足 {conditions_met}/4 项节拍（需要 ≥2）"
            )

    # ── 裁决 ──
    # Phase 2: 不 FAIL，只 WARNING
    if failing > 0:
        status = "WARNING"
        violations.append(f"{failing}/{len(scenes)} 场景节拍不足")
    else:
        status = "PASS"

    report = {
        "status": status,
        "final_decision": status,
        "chapter_no": chapter_no,
        "scenes_analyzed": len(scenes),
        "scene_reports": scene_reports,
        "scenes_passing": passing,
        "scenes_failing": failing,
        "dialogue_beat_pass": failing == 0,
        "violations": violations,
        "warnings": warnings,
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Dialogue Beat Guard")
    parser.add_argument("content_file", help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    content = Path(args.content_file).read_text(encoding="utf-8")
    report = run_dialogue_beat_check(content, args.chapter_no)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if report["status"] == "WARNING":
        print(f"\n[WARN] Dialogue beats: {report['scenes_failing']}/{report['scenes_analyzed']} scenes need more beats")
    else:
        print(f"\n[OK] Dialogue beat check passed ({report['scenes_analyzed']} scenes)")


if __name__ == "__main__":
    main()
