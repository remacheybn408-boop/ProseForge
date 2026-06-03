#!/usr/bin/env python3
"""
padding_guard.py — 防水文证据门禁

不只检查 padding_detected=true/false，还计算 padding_score、padding_level、
和各类水文特征的详细证据。

检测类型:
  repeated_explanation — 同一设定反复解释
  empty_inner_monologue — 连续心理活动无动作
  dialogue_echo — 对话双方反复确认同一信息
  low_delta_paragraph — 段落无推进
  tail_padding — 章节末尾无关总结

用法:
  python scripts/padding_guard.py content.txt [--output report.json]
"""

import re, json, sys, argparse
from pathlib import Path


def count_repeated_explanations(content):
    """检测同一设定被反复解释的次数"""
    # 搜索设定类关键词在全文中的重复模式
    setting_keywords = [
        r'(灵气|灵根|灵矿|修炼|境界|功法|丹药|法宝|阵法|符文)',
        r'(规则|定律|原理|机制|模型|理论|假设)',
        r'(世界观|设定|背景|来源|起源)',
    ]
    count = 0
    for pattern in setting_keywords:
        matches = re.findall(pattern, content)
        # 如果同一个设定词出现超过合理次数且伴随解释性语句
        explanation_signal = re.findall(r'(也就是说|简单来说|换言之|换句话说|说白了|意味着)', content)
        if len(matches) > 8 and len(explanation_signal) > 2:
            count += len(explanation_signal)
    return min(count, 20)  # cap


def count_empty_inner_monologue(content):
    """检测空转心理活动"""
    sentences = re.findall(r'[^。！？\n]+[。！？]', content)
    count = 0
    inner_patterns = [
        r'他(知道|明白|意识到|觉得|感觉|想起|想起|想到)',
        r'她(知道|明白|意识到|觉得|感觉|想起|想起|想到)',
    ]

    for i, s in enumerate(sentences):
        for pat in inner_patterns:
            if re.search(pat, s):
                # 检查前后是否有实际行动
                has_action_before = i > 0 and re.search(r'(蹲|站|走|跑|拿|放|推|拉|按|握|劈|搬|涂|贴|刮|洗|抓)', sentences[i-1])
                has_action_after = i < len(sentences)-1 and re.search(r'(蹲|站|走|跑|拿|放|推|拉|按|握|劈|搬|涂|贴|刮|洗|抓)', sentences[i+1])
                if not has_action_before and not has_action_after:
                    count += 1
    return count


def count_dialogue_echo(content):
    """检测对话双方反复确认同一信息"""
    # 找连续的对话对
    dialogue_pairs = re.findall(r'"([^"]{15,80})"[^"]{0,50}"([^"]{15,80})"', content)
    echo_count = 0
    for a, b in dialogue_pairs:
        # 提取关键词对比
        a_kw = set(re.findall(r'[\u4e00-\u9fff]{2,4}', a))
        b_kw = set(re.findall(r'[\u4e00-\u9fff]{2,4}', b))
        overlap = len(a_kw & b_kw)
        if overlap > 5:
            echo_count += 1
    return echo_count


def count_low_delta_paragraphs(content):
    """检测无推进的段落"""
    paragraphs = [p.strip() for p in content.split("\n") if p.strip() and len(p.strip()) > 30]
    low_delta = 0

    advancement_markers = [
        r'(蹲|站|走|跑|拿|放|推|拉|按|握|劈|搬|涂|贴|刮|洗|抓|踢|踩|跳|爬)',  # 动作
        r'"([^"]{5,})"',  # 对话
        r'(发现|察觉|注意|看到|听到|闻到|感到)',  # 新感知
        r'(突然|忽然|竟然|居然|不料|没想到)',  # 转折
        r'(变化|改变|转变|不同|异常)',  # 变化
    ]

    for p in paragraphs:
        has_advancement = any(re.search(m, p) for m in advancement_markers)
        if not has_advancement:
            low_delta += 1

    return low_delta


def check_tail_padding(content):
    """检测章节末尾是否有灌水总结"""
    tail = content[-400:] if len(content) > 400 else content

    padding_signals = [
        r'(总之|总而言之|综上所述|总的来说)',
        r'(他知道.{5,40}了)',
        r'(他终于.{5,30}了)',
        r'(一切.{5,20}(?:都|就|将|会))',
        r'(这就是.{5,30}(?:的|了))',
    ]

    signal_count = sum(len(re.findall(p, tail)) for p in padding_signals)
    return signal_count > 2, signal_count


def run_padding_check(content, chapter_type="normal"):
    """主入口：运行防水文检查"""

    repeated = count_repeated_explanations(content)
    empty_mono = count_empty_inner_monologue(content)
    echo = count_dialogue_echo(content)
    low_delta = count_low_delta_paragraphs(content)
    tail_pad, tail_signal_count = check_tail_padding(content)

    # ── 计算 padding_score ──
    score = 0
    evidence = []

    if repeated > 0:
        score += min(repeated * 5, 25)
        evidence.append({"type": "repeated_explanation", "count": repeated, "score_impact": min(repeated * 5, 25)})
    if empty_mono > 3:
        score += min(empty_mono * 3, 20)
        evidence.append({"type": "empty_inner_monologue", "count": empty_mono, "score_impact": min(empty_mono * 3, 20)})
    if echo > 2:
        score += min(echo * 4, 15)
        evidence.append({"type": "dialogue_echo", "count": echo, "score_impact": min(echo * 4, 15)})
    if low_delta > 5:
        extra = min((low_delta - 5) * 2, 25)
        score += extra
        evidence.append({"type": "low_delta_paragraphs", "count": low_delta, "score_impact": extra})
    if tail_pad:
        score += 15
        evidence.append({"type": "tail_padding", "count": tail_signal_count, "score_impact": 15})

    score = min(score, 100)

    # ── 判定 padding_level ──
    if score <= 20:
        level = "none"
    elif score <= 40:
        level = "warning"
    elif score <= 60:
        level = "review"
    else:
        level = "fail"

    detected = level in ("review", "fail")

    report = {
        "padding_detected": detected,
        "padding_score": score,
        "padding_level": level,
        "padding_evidence": evidence,
        "effective_scene_delta_count": 0,  # filled by pipeline or scene_delta_guard
        "low_delta_paragraph_count": low_delta,
        "repeated_explanation_count": repeated,
        "empty_inner_monologue_count": empty_mono,
        "dialogue_echo_count": echo,
        "tail_padding_detected": tail_pad
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Padding Guard")
    parser.add_argument("content_file", help="章节 TXT 文件")
    parser.add_argument("--output", default=None, help="输出 report JSON 路径")
    args = parser.parse_args()

    content = Path(args.content_file).read_text(encoding="utf-8")
    report = run_padding_check(content)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[OK] report saved: {args.output}")

    if report["padding_level"] == "fail":
        print(f"\n[FAIL] Padding gate failed (score={report['padding_score']})")
        sys.exit(1)
    elif report["padding_detected"]:
        print(f"\n[WARN] Padding detected (level={report['padding_level']}, score={report['padding_score']})")
    else:
        print(f"\n[OK] No padding detected (score={report['padding_score']})")


if __name__ == "__main__":
    main()
