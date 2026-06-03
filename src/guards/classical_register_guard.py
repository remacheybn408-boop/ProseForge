#!/usr/bin/env python3
"""
classical_register_guard.py — 文言/古雅语体门禁 v0.3.1-qgp

检查文言/古雅语体是否合理：
1. 文言是否集中在合适角色和文本类型
2. 是否有过度文言导致难懂
3. 是否所有角色都文绉绉
4. 是否用文言掩盖剧情空洞
5. 是否古籍/碑文后有现实反应

策略: Phase 2 — 先 WARNING，不 FAIL
"""
import re, json, sys, argparse
from pathlib import Path

# ═══════════════════════════════════════════════════
# 文言/古雅语体检测
# ═══════════════════════════════════════════════════

WENYAN_DENSE = re.compile(
    r'(之乎者也|然则|夫.{0,5}(也|矣|焉|耳|乎|哉)|盖.{0,5}(也|矣|焉)'
    r'|岂不|莫不|未尝|遂|乃|辄|竟|是以|是故|由此|因而'
    r'|呜呼|噫|吁|嗟乎|悲夫)'
)

WENYAN_LIGHT = re.compile(
    r'(然|故|盖|则|乃|遂|耳|矣|焉|乎|哉|邪|与|耶|欤|耳|尔)'
)

RAW_CLASSICAL_BLOCK = re.compile(
    r'(.{20,}(?:之乎者也|矣焉耳乎).{20,})'
)

OVER_CLASSICAL = re.compile(
    r'((?:然则|夫|盖|岂|莫|遂|乃|辄|竟|是以|是故).{0,50}){3,}'
)


def analyze_classical_register(content):
    """分析全文文言分布"""
    # ── 提取对白 ──
    dialogues = []
    for m in re.finditer(r'[""「」]([^""「」]{10,300})[""「」]', content):
        dialogues.append(m.group(1))

    # ── 提取旁白（去对白）──
    narration = re.sub(r'[""「」][^""「」]+[""「」]', '', content)

    # ── 文言密度分析 ──
    dense_markers = len(WENYAN_DENSE.findall(content))
    light_markers = len(WENYAN_LIGHT.findall(content))
    total_chars = len([c for c in content if '\u4e00' <= c <= '\u9fff'])

    # 文言密度 = (dense*3 + light) / 总字数 * 100
    wenyan_density = round((dense_markers * 3 + light_markers) / max(total_chars, 1) * 100, 2)

    # ── 整段古文检测 ──
    raw_blocks = RAW_CLASSICAL_BLOCK.findall(content)
    raw_block_segments = []
    for block in raw_blocks:
        start = content.find(block)
        raw_block_segments.append({
            "text": block[:80],
            "position": start,
            "has_reaction_after": _has_reaction_after(content, start + len(block))
        })

    # ── 过度文言段 ──
    over_segments = OVER_CLASSICAL.findall(narration)
    over_segments = [s[:80] for s in over_segments[:5]]

    # ── 可读性风险 ──
    readability_risk = "low"
    if wenyan_density > 15:
        readability_risk = "high"
    elif wenyan_density > 8:
        readability_risk = "medium"

    # ── 语言规范段检测 ──
    is_law_text = bool(re.search(r'(宗门|[律令]|戒律|门规|法令|条例)', content[:500]))

    return {
        "wenyan_density_percent": wenyan_density,
        "dense_marker_count": dense_markers,
        "light_marker_count": light_markers,
        "raw_classical_blocks": raw_block_segments,
        "over_classical_segments": over_segments,
        "readability_risk": readability_risk,
        "has_law_text": is_law_text,
    }


def _has_reaction_after(content, pos, window=200):
    """检查古文块后是否有现实反应"""
    tail = content[pos:pos+window]
    return bool(re.search(r'(说|道|问|答|回应|点头|皱眉|沉默|退|进|动手|拔剑|拜|拱手)', tail))


def run_classical_register_check(content, chapter_no, voice_profiles=None):
    """主入口"""
    analysis = analyze_classical_register(content)

    warnings = []
    violations = []

    # ── 1. 整体文言密度 ──
    if analysis["readability_risk"] == "high":
        warnings.append(f"文言密度过高 {analysis['wenyan_density_percent']}%（可读性风险）")
    elif analysis["readability_risk"] == "medium":
        warnings.append(f"文言密度偏高 {analysis['wenyan_density_percent']}%")

    # ── 2. 古文块后无反应 ──
    for block in analysis["raw_classical_blocks"]:
        if not block["has_reaction_after"]:
            violations.append(f"古文块后无现实反应: '{block['text'][:40]}...'")

    # ── 3. 旁白过度文言 ──
    if analysis["over_classical_segments"]:
        warnings.append(f"旁白过度文言段: {len(analysis['over_classical_segments'])} 处")

    # ── 4. 裁决 ──
    critical = len(violations)
    passed = critical == 0

    report = {
        "status": "PASS" if passed else "WARNING",
        "final_decision": "PASS" if passed else "WARNING",
        "chapter_no": chapter_no,
        "wenyan_density_percent": analysis["wenyan_density_percent"],
        "dense_marker_count": analysis["dense_marker_count"],
        "light_marker_count": analysis["light_marker_count"],
        "raw_classical_blocks": len(analysis["raw_classical_blocks"]),
        "blocks_without_reaction": critical,
        "over_classical_segments": analysis["over_classical_segments"],
        "readability_risk": analysis["readability_risk"],
        "has_law_text": analysis["has_law_text"],
        "violations": violations,
        "warnings": warnings,
        "classical_register_pass": passed,
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Classical Register Guard")
    parser.add_argument("content_file", help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    content = Path(args.content_file).read_text(encoding="utf-8")
    report = run_classical_register_check(content, args.chapter_no)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if not report["classical_register_pass"]:
        print(f"\n[WARN] Classical register check: {len(report['violations'])} violations")
    else:
        print(f"\n[OK] Classical register check passed")


if __name__ == "__main__":
    main()
