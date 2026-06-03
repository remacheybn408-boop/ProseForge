#!/usr/bin/env python3
"""
concrete_hook_guard.py — 具体钩子门禁 v0.3.1-qgp

检查章节结尾钩子是否具体：
禁止空泛危机句、命运齿轮句。
要求结尾钩子必须绑定一种 anchor: object / person / location / relationship / cost

策略: Phase 2 — 先 WARNING，但明确指出缺失的 anchor 类型
"""
import re, json, sys, argparse
from pathlib import Path

# ═══════════════════════════════════════════════════
# 空泛钩子（禁止）
# ═══════════════════════════════════════════════════

VAGUE_HOOK_PATTERNS = [
    (re.compile(r'真正的危机才(刚刚|刚要|开始)'), "空泛危机"),
    (re.compile(r'风暴(即将|就要|马上)来临'), "空泛风暴"),
    (re.compile(r'更大的阴谋正在靠近'), "空泛阴谋"),
    (re.compile(r'没人知道等待.{1,10}的(是什么|会是)'), "空泛悬念"),
    (re.compile(r'命运的齿轮(开始|已经|再次)转动'), "命运齿轮"),
    (re.compile(r'命运的(轨迹|捉弄|安排)'), "命运句"),
    (re.compile(r'新的.{0,5}(篇章|时代|纪元|旅程|冒险)即(将|要)开始'), "空泛新篇"),
    (re.compile(r'一切.{0,5}刚刚开始'), "空泛一切开始"),
    (re.compile(r'故事.{0,5}才(刚刚|刚要)开始'), "空泛故事开始"),
    (re.compile(r'真正的(考验|挑战|危险|试炼)才(刚刚|刚要)'), "空泛考验"),
]

# ═══════════════════════════════════════════════════
# 具体锚点检测
# ═══════════════════════════════════════════════════

OBJECT_ANCHOR = re.compile(
    r'(裂开|碎了|裂了|断了|亮了|发光|消失|出现|露出|显现)'
    r'|(里面|底下|背后|后面|前面|上面).{0,15}(露|现|出|有)'
    r'|(碎|裂|残|破|断)'
)

PERSON_ANCHOR = re.compile(
    r'(站着|站着|出现|走了|来了|消失|回来|回来|返回).{0,10}(的|了)'
    r'|(不是.{1,10}(而是|竟然是|原来是))'
    r'|(门外|身后|前面|后面|旁边).{0,10}(站着|出现|有)'
)

LOCATION_ANCHOR = re.compile(
    r'(不见了|消失了|变了|成了|变成了|出现).{0,10}(了|的)'
    r'|(入口|出口|洞口|门口|路|通道|门).{0,15}(不见|消失|变|出现)'
    r'|(回头|转身|抬头|低头).{0,15}(不见|没了|变了|出现了)'
)

RELATIONSHIP_ANCHOR = re.compile(
    r'(剑|刀|匕首|武器|手).{0,15}(横|指|对准|放在|抵在).{0,10}(喉|胸口|面前|脖子)'
    r'|(声音很轻|压低声音|冷冷地|盯着).{0,20}(你|我|他|她)'
    r'|(不是).{0,10}(本门|自己人|朋友|盟友|同伴)'
    r'|(原来|其实|竟然).{0,10}(是|不是)'
)

COST_ANCHOR = re.compile(
    r'(却|但|然而|可|不过).{0,15}(发现|发现自己|发现已|发现已经)'
    r'|(终于|总算).{0,10}(但是|但|却|然而|可)'
    r'|(付出|失去|牺牲|放弃|消耗|烧掉|耗光|用了).{0,10}(了|的)'
    r'|(再也|再不能|已经).{0,10}(不|没|无)'
)


def analyze_ending(content, tail_chars=400):
    """分析结尾的钩子质量"""
    tail = content[-tail_chars:] if len(content) > tail_chars else content
    # 只取最后一个段落群（最后 3 个非空段落）
    paragraphs = [p.strip() for p in tail.split('\n') if p.strip()]
    ending_paragraphs = paragraphs[-3:] if len(paragraphs) >= 3 else paragraphs
    ending = '\n'.join(ending_paragraphs)

    anchors = {
        "object": bool(OBJECT_ANCHOR.search(ending)),
        "person": bool(PERSON_ANCHOR.search(ending)),
        "location": bool(LOCATION_ANCHOR.search(ending)),
        "relationship": bool(RELATIONSHIP_ANCHOR.search(ending)),
        "cost": bool(COST_ANCHOR.search(ending)),
    }

    # ── 检测空泛钩子 ──
    vague_matches = []
    for pattern, label in VAGUE_HOOK_PATTERNS:
        m = pattern.search(ending)
        if m:
            vague_matches.append({
                "pattern": label,
                "text": m.group()[:60]
            })

    # ── 归类 ──
    anchor_count = sum(1 for v in anchors.values() if v)
    anchor_types = [k for k, v in anchors.items() if v]
    has_vague = len(vague_matches) > 0

    return {
        "ending_text": ending[:200],
        "anchor_count": anchor_count,
        "anchor_types": anchor_types,
        "anchors": anchors,
        "vague_hooks": vague_matches,
        "has_vague": has_vague,
    }


def run_concrete_hook_check(content, chapter_no):
    """主入口"""
    analysis = analyze_ending(content)

    warnings = []
    violations = []

    # ── 1. 空泛钩子检查 ──
    if analysis["has_vague"]:
        for v in analysis["vague_hooks"]:
            violations.append(f"空泛钩子 [{v['pattern']}]: '{v['text']}'")

    # ── 2. 锚点检查 ──
    if analysis["anchor_count"] == 0:
        warnings.append("结尾无具体锚点: 建议绑定物件/人物/地点/关系/代价")

    # ── 3. 裁决 ──
    if violations or analysis["anchor_count"] == 0:
        status = "WARNING"
    else:
        status = "PASS"

    # 确定主要钩子类型
    hook_type = analysis["anchor_types"][0] if analysis["anchor_types"] else "none"

    report = {
        "status": status,
        "final_decision": status,
        "chapter_no": chapter_no,
        "hook_type": hook_type,
        "hook_anchor": "; ".join(analysis["anchor_types"]) if analysis["anchor_types"] else "无具体锚点",
        "anchor_count": analysis["anchor_count"],
        "anchor_types": analysis["anchor_types"],
        "vague_hook_found": analysis["has_vague"],
        "vague_hooks": analysis["vague_hooks"],
        "anchors_detected": analysis["anchors"],
        "concrete_hook_pass": status == "PASS",
        "violations": violations,
        "warnings": warnings,
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Concrete Hook Guard")
    parser.add_argument("content_file", help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    content = Path(args.content_file).read_text(encoding="utf-8")
    report = run_concrete_hook_check(content, args.chapter_no)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if report["status"] == "WARNING":
        print(f"\n[WARN] Concrete hook: {'空泛钩子' if report['vague_hook_found'] else '无锚点'}")
    else:
        print(f"\n[OK] Concrete hook: {report['hook_type']}")


if __name__ == "__main__":
    main()
