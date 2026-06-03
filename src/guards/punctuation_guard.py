#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
标点节奏门禁 (PunctuationGuard)
===============================
统计长破折号、省略号、感叹号等标点的使用密度，
按单章阈值判定 PASS / WARNING / STRONG_WARNING / FAIL。

用法:
    from scripts.guards.punctuation_guard import run_punctuation_check, analyze_chapter

    result = run_punctuation_check(content, chapter_no=1)  # guard 兼容入口
    result = analyze_chapter("path/to/chapter.txt")         # 文件分析入口
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

# 长破折号 "——" (成对出现算 1 组) — v0.5.5 收紧：用户偏好极低密度
DASH_PAIR_PASS = (0, 2)       # 0-2 组 PASS
DASH_PAIR_WARN = 3            # >=3 组 WARNING
DASH_PAIR_STRONG = 5          # >=5 组 STRONG WARNING
DASH_PAIR_FAIL = 8            # >=8 组 FAIL

DASH_PER_KW_WARN = 2          # 每千字 >2 组 WARNING
DASH_PER_KW_FAIL = 4          # 每千字 >4 组 FAIL

DASH_SAME_PARA_WARN = 2       # 同一段内 >=2 组 WARNING
DASH_SAME_PARA_FAIL = 3       # 同一段内 >=3 组 FAIL
DASH_CONSEC_PARA_WARN = 3     # 连续 >=3 段出现 "——" WARNING

ELLIPSIS_WARN = 12            # 省略号 >12 组 WARNING
ELLIPSIS_FAIL = 20            # 省略号 >20 组 FAIL

EXCLAM_WARN = 15              # 感叹号 >15 个 WARNING
EXCLAM_FAIL = 25              # 感叹号 >25 个 FAIL

# 各种省略号形式
ELLIPSIS_PATTERNS = [
    r"……",
    r"\.\.\.",        # 英文省略号
    r"。{3,}",        # "。。。" 形式
]

# 感叹号
EXCLAM_PATTERNS = [r"！", r"!"]

# 长破折号
DASH_PATTERN = "——"
SINGLE_DASH_PATTERN = "—"   # 单破折号（非成对）


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _count_matches(text: str, patterns: List[str]) -> int:
    """统计 text 中所有 pattern 的匹配总数。"""
    total = 0
    for pat in patterns:
        total += len(re.findall(pat, text))
    return total


def _split_paragraphs(text: str) -> List[str]:
    """将文本按空行/换行切分为段落列表，保留有内容的段落。"""
    # 先按连续换行拆分
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _word_count(text: str) -> int:
    """估算中文字数（仅统计中文字符）。"""
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    return len(chinese_chars)


def _count_dash_pairs(text: str) -> int:
    """统计成对 "——" 的组数。相邻两个 "——" 计为 1 组。"""
    # 找到所有 "——" 的位置
    positions = [m.start() for m in re.finditer(re.escape(DASH_PATTERN), text)]
    pairs = 0
    i = 0
    while i < len(positions) - 1:
        # 相邻两个视为一对
        pairs += 1
        i += 2
    return pairs


def _count_single_dashes(text: str) -> int:
    """统计未成对的单破折号 "—" 数量。
    排除 "——" 中的部分：先替换掉 "——"，再统计 "—"。"""
    cleaned = text.replace(DASH_PATTERN, "")
    return cleaned.count(SINGLE_DASH_PATTERN)


def _count_all_dashes(text: str) -> int:
    """统计所有单破折号（包括 "——" 中的）。"""
    return text.count(SINGLE_DASH_PATTERN)


# ---------------------------------------------------------------------------
# 破折号分类 (4 类)
# ---------------------------------------------------------------------------

def _classify_dashes(text: str, paragraphs: List[str]) -> Dict[str, List[Dict]]:
    """对破折号使用进行分类。

    返回 {"解释型": [...], "插入型": [...], "悬念型": [...], "对话拖音/喜剧型": [...]}
    """
    result = {
        "解释型": [],
        "插入型": [],
        "悬念型": [],
        "对话拖音/喜剧型": [],
    }

    # 1) 解释型: "不是...——而是..." 类模式
    explanatory_ctx = [
        r"(?:不是|并非|并非如此)[^—]{0,20}——",
        r"——[^—]{0,20}(?:而是|而是说|就是说|也即|换言之)",
        r"(?:所谓|即|也就是)[^—]{0,20}——",
    ]
    for pat in explanatory_ctx:
        for m in re.finditer(pat, text):
            ctx = text[max(0, m.start() - 15):min(len(text), m.end() + 15)]
            result["解释型"].append({
                "context": ctx.replace("\n", " "),
                "position": m.start(),
            })

    # 2) 插入型: 成对 "——" 包围插入语
    insert_pat = re.compile(r"——.+?——")
    for m in insert_pat.finditer(text):
        result["插入型"].append({
            "context": m.group()[:50],
            "position": m.start(),
        })

    # 3) 悬念型: 段落末尾的 "——"
    for idx, para in enumerate(paragraphs):
        para_stripped = para.rstrip()
        if para_stripped.endswith("——"):
            # 排除解释型和插入型中已计入的（简单去重）
            result["悬念型"].append({
                "context": para_stripped[-30:] if len(para_stripped) > 30 else para_stripped,
                "paragraph": idx + 1,
            })

    # 4) 对话拖音/喜剧型: 词间破折号 "掉——水——里——了"
    word_interleave_pat = re.compile(r"[\u4e00-\u9fff]——[\u4e00-\u9fff]")
    for m in word_interleave_pat.finditer(text):
        ctx = text[max(0, m.start() - 5):min(len(text), m.end() + 5)]
        result["对话拖音/喜剧型"].append({
            "context": ctx.replace("\n", " "),
            "position": m.start(),
        })

    return result


# ---------------------------------------------------------------------------
# 段落规则检查
# ---------------------------------------------------------------------------

def _check_paragraph_rules(paragraphs: List[str]) -> List[Dict]:
    """段落级别破折号规则检查。"""
    issues = []

    # 每段内 "——" 出现次数
    para_dash_counts = []
    for idx, para in enumerate(paragraphs):
        count = para.count(DASH_PATTERN)
        # Drag dialogue: "掉——水——里——了" — cap paragraph dash count at 1
        if count >= 2 and re.search(r'[\u4e00-\u9fff]——[\u4e00-\u9fff]', para):
            drag_ratio = len(re.findall(r'[\u4e00-\u9fff]——[\u4e00-\u9fff]', para)) / max(count, 1)
            if drag_ratio > 0.5:
                count = 1  # Treat drag dialogue as single dash
        para_dash_counts.append((idx, count))

        if count >= DASH_SAME_PARA_FAIL:
            issues.append({
                "level": "FAIL",
                "type": "段落破折号过多",
                "message": f"第 {idx + 1} 段出现 {count} 组 '——'，超过 {DASH_SAME_PARA_FAIL - 1} 组上限",
                "evidence": para[:80] + ("..." if len(para) > 80 else ""),
                "suggestion": "控制每段破折号数量，分散表达或改用其他标点",
            })
        elif count >= DASH_SAME_PARA_WARN:
            issues.append({
                "level": "WARNING",
                "type": "段落破折号偏多",
                "message": f"第 {idx + 1} 段出现 {count} 组 '——'，超过 {DASH_SAME_PARA_WARN - 1} 组建议上限",
                "evidence": para[:80] + ("..." if len(para) > 80 else ""),
                "suggestion": "每段建议不超过 1 组破折号，避免视觉疲劳",
            })

    # 连续 3 段都出现 "——"
    consec = 0
    for idx, count in para_dash_counts:
        if count > 0:
            consec += 1
            if consec >= DASH_CONSEC_PARA_WARN:
                start_para = idx - consec + 2  # 转为 1-based
                end_para = idx + 1
                issues.append({
                    "level": "WARNING",
                    "type": "连续段落破折号",
                    "message": f"第 {start_para} 到第 {end_para} 段连续 {consec} 段出现 '——'",
                    "evidence": f"连续 {consec} 段包含破折号，节奏可能过于急促",
                    "suggestion": "在连续段落中穿插无破折号的段落，调整叙事节奏",
                })
                consec = 0  # 重置，避免重复报告
        else:
            consec = 0

    return issues


# ---------------------------------------------------------------------------
# 主检查逻辑
# ---------------------------------------------------------------------------

def _build_findings(text: str, paragraphs: List[str], word_cnt: int,
                    dash_pairs: int, total_dashes: int,
                    ellipsis_count: int, excl_count: int) -> List[Dict]:
    """汇总所有 findings。"""
    findings = []

    # --- 破折号总量 ---
    # Skip density checks for very short text (<50 chars)
    if word_cnt < 50:
        pass  # Short text exempt from dash density checks
    elif dash_pairs >= DASH_PAIR_FAIL:
        findings.append({
            "level": "FAIL",
            "type": "破折号总量超标",
            "message": f"单章 '——' 共 {dash_pairs} 组，超过 {DASH_PAIR_FAIL - 1} 组上限",
            "evidence": f"共 {dash_pairs} 组成对破折号",
            "suggestion": "大幅削减破折号使用，或拆分章节",
        })
    elif dash_pairs >= DASH_PAIR_STRONG:
        findings.append({
            "level": "STRONG_WARNING",
            "type": "破折号总量偏高",
            "message": f"单章 '——' 共 {dash_pairs} 组，处于 {DASH_PAIR_STRONG}-{DASH_PAIR_FAIL-1} 组区间",
            "evidence": f"共 {dash_pairs} 组成对破折号",
            "suggestion": "建议将破折号控制在 4 组以内",
        })
    elif dash_pairs >= DASH_PAIR_WARN:
        findings.append({
            "level": "WARNING",
            "type": "破折号总量偏多",
            "message": f"单章 '——' 共 {dash_pairs} 组，超过 {DASH_PAIR_WARN - 1} 组建议上限",
            "evidence": f"共 {dash_pairs} 组成对破折号",
            "suggestion": "可适当减少破折号，控制在 2 组以内为佳",
        })

    # --- 每千字密度 ---
    if word_cnt > 100:  # Only check density for texts > 100 chars
        per_kw = (dash_pairs / word_cnt) * 1000
        if per_kw > DASH_PER_KW_FAIL:
            findings.append({
                "level": "FAIL",
                "type": "破折号密度超标",
                "message": f"每千字 '——' {per_kw:.1f} 组，超过 {DASH_PER_KW_FAIL} 组上限",
                "evidence": f"{dash_pairs} 组 / {word_cnt} 字 = {per_kw:.1f} 组/千字",
                "suggestion": "章节字数不足或破折号过多，考虑扩充内容或削减破折号",
            })
        elif per_kw > DASH_PER_KW_WARN:
            findings.append({
                "level": "WARNING",
                "type": "破折号密度偏高",
                "message": f"每千字 '——' {per_kw:.1f} 组，超过 {DASH_PER_KW_WARN} 组建议上限",
                "evidence": f"{dash_pairs} 组 / {word_cnt} 字 = {per_kw:.1f} 组/千字",
                "suggestion": "每千字破折号建议控制在 2 组以内",
            })

    # --- 段落规则 ---
    para_issues = _check_paragraph_rules(paragraphs)
    findings.extend(para_issues)

    # --- 省略号 ---
    if ellipsis_count > ELLIPSIS_FAIL:
        findings.append({
            "level": "FAIL",
            "type": "省略号超标",
            "message": f"省略号共 {ellipsis_count} 组，超过 {ELLIPSIS_FAIL} 组上限",
            "evidence": f"共 {ellipsis_count} 处省略号",
            "suggestion": "大幅减少省略号，用具体描写替代留白",
        })
    elif ellipsis_count > ELLIPSIS_WARN:
        findings.append({
            "level": "WARNING",
            "type": "省略号偏多",
            "message": f"省略号共 {ellipsis_count} 组，超过 {ELLIPSIS_WARN} 组建议上限",
            "evidence": f"共 {ellipsis_count} 处省略号",
            "suggestion": "省略号过多会让文风显得拖沓，适度用句号替代",
        })

    # --- 感叹号 ---
    if excl_count > EXCLAM_FAIL:
        findings.append({
            "level": "FAIL",
            "type": "感叹号超标",
            "message": f"感叹号共 {excl_count} 个，超过 {EXCLAM_FAIL} 个上限",
            "evidence": f"共 {excl_count} 个感叹号",
            "suggestion": "大幅减少感叹号，用文字本身传达情绪力度",
        })
    elif excl_count > EXCLAM_WARN:
        findings.append({
            "level": "WARNING",
            "type": "感叹号偏多",
            "message": f"感叹号共 {excl_count} 个，超过 {EXCLAM_WARN} 个建议上限",
            "evidence": f"共 {excl_count} 个感叹号",
            "suggestion": "感叹号过多会让情绪表达单调，适当用句号或反问句替代",
        })

    return findings


def _determine_status(findings: List[Dict]) -> str:
    """根据 findings 的 level 确定最终状态。"""
    levels = [f["level"] for f in findings]
    if "FAIL" in levels:
        return "FAIL"
    if "STRONG_WARNING" in levels:
        return "WARNING"  # STRONG_WARNING 也归入 WARNING（兼容 guard 三态）
    if "WARNING" in levels:
        return "WARNING"
    return "PASS"


def _compute_score(findings: List[Dict]) -> int:
    """计算综合得分 (0-100)。"""
    score = 100
    for f in findings:
        level = f["level"]
        if level == "FAIL":
            score -= 15
        elif level == "STRONG_WARNING":
            score -= 8
        elif level == "WARNING":
            score -= 4
    return max(0, score)


# ---------------------------------------------------------------------------
# 公开入口
# ---------------------------------------------------------------------------

def run_punctuation_check(content: str, chapter_no: int = 0) -> Dict:
    """对章节文本执行标点节奏门禁检查 (guard 兼容入口)。

    Args:
        content: 章节文本内容
        chapter_no: 章节编号

    Returns:
        {
            "status": "PASS" | "WARNING" | "FAIL",
            "score": int,           # 0-100
            "stats": {...},
            "findings": [...],
            "issues": [...]         # guard 兼容: status != PASS 时非空
        }
    """
    if not content or not content.strip():
        return {
            "status": "PASS",
            "score": 100,
            "stats": {
                "chapter_no": chapter_no,
                "word_count": 0,
                "total_dashes": 0,
                "dash_pairs": 0,
                "dash_single": 0,
                "ellipsis_count": 0,
                "exclamation_count": 0,
                "paragraphs": 0,
            },
            "findings": [],
            "issues": [],
        }

    paragraphs = _split_paragraphs(content)
    word_cnt = _word_count(content)

    # 统计
    total_dashes = _count_all_dashes(content)
    dash_pairs = _count_dash_pairs(content)
    single_dashes = _count_single_dashes(content)
    ellipsis_count = _count_matches(content, ELLIPSIS_PATTERNS)
    excl_count = _count_matches(content, EXCLAM_PATTERNS)

    # 破折号分类
    dash_classification = _classify_dashes(content, paragraphs)

    # 汇总 findings
    findings = _build_findings(content, paragraphs, word_cnt, dash_pairs,
                               total_dashes, ellipsis_count, excl_count)

    status = _determine_status(findings)
    score = _compute_score(findings)

    stats = {
        "chapter_no": chapter_no,
        "word_count": word_cnt,
        "total_dashes": total_dashes,
        "dash_pairs": dash_pairs,
        "dash_single": single_dashes,
        "ellipsis_count": ellipsis_count,
        "exclamation_count": excl_count,
        "paragraphs": len(paragraphs),
        "dash_classification": {
            k: len(v) for k, v in dash_classification.items()
        },
        "dash_classification_detail": dash_classification,
    }

    result = {
        "status": status,
        "score": score,
        "stats": stats,
        "findings": findings,
        "issues": [] if status == "PASS" else [
            {"level": f["level"], "type": f["type"], "message": f["message"]}
            for f in findings
        ],
    }

    # 生成 JSON 报告
    _generate_report(result, chapter_no)

    return result


def analyze_chapter(filepath: str) -> Dict:
    """从文件读取章节并分析。

    Args:
        filepath: 章节文件路径

    Returns:
        与 run_punctuation_check 相同的 dict
    """
    path = Path(filepath)
    if not path.exists():
        return {
            "status": "FAIL",
            "score": 0,
            "stats": {},
            "findings": [{
                "level": "FAIL",
                "type": "文件错误",
                "message": f"文件不存在: {filepath}",
                "evidence": "",
                "suggestion": "检查文件路径是否正确",
            }],
            "issues": [{"level": "FAIL", "type": "文件错误", "message": f"文件不存在: {filepath}"}],
        }

    content = path.read_text(encoding="utf-8")

    # 尝试从文件名中提取章节号
    chapter_no = 0
    stem = path.stem
    numbers = re.findall(r"\d+", stem)
    if numbers:
        chapter_no = int(numbers[-1])

    return run_punctuation_check(content, chapter_no)


def _generate_report(result: Dict, chapter_no: int) -> None:
    """将检查结果输出为 JSON 报告。"""
    report_dir = Path("exports/reports/punctuation_guard")
    report_dir.mkdir(parents=True, exist_ok=True)

    filename = f"chapter_{chapter_no:03d}_punctuation_report.json"
    filepath = report_dir / filename

    # 报告中排除过于冗长的分类详情
    report_data = {
        "status": result["status"],
        "score": result["score"],
        "stats": {
            k: v for k, v in result["stats"].items()
            if k != "dash_classification_detail"
        },
        "findings": result["findings"],
        "issues": result["issues"],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"[PunctuationGuard] 报告已生成: {filepath}")


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python punctuation_guard.py <filepath>")
        sys.exit(1)

    result = analyze_chapter(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
