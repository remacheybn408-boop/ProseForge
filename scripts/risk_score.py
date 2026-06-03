#!/usr/bin/env python3
"""
risk_score.py — 章节风险评分模块 v0.5.0

8 个风险维度：AI腔风险、水文风险、连续性风险、人设跑偏风险、
设定幻觉风险、追读力风险、梗出戏风险、方言过量风险。

优先复用现有 guard 模块做启发式评分；如果 guard 模块不可用，降级为基础规则检测。

用法:
  from scripts.risk_score import RiskScorer
  scorer = RiskScorer(db_path="data/novel_memory.db")
  result = scorer.score_chapter(content, chapter_no=5)
  # result = {"risk_levels": {...}, "total_risk": "MEDIUM", ...}
"""

import re
import sys
import json
import logging
from pathlib import Path
from typing import Optional

# ── Ensure project root is importable ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════
# 8 个风险维度定义
# ═══════════════════════════════════════════════════

RISK_DIMENSIONS = [
    "ai_style",       # AI腔风险
    "filler",          # 水文风险
    "continuity",      # 连续性风险
    "character_voice", # 人设跑偏风险
    "hallucination",   # 设定幻觉风险
    "reader_pull",     # 追读力风险
    "meme",            # 梗出戏风险
    "dialect",         # 方言过量风险
]

LEVEL_THRESHOLDS = {
    "low":    0.0,
    "medium": 0.30,
    "high":   0.60,
    "block":  0.85,
}


def _score_to_level(score: float) -> str:
    """Convert a 0.0-1.0 score to a risk level label."""
    if score < 0:
        return "low"
    if score >= LEVEL_THRESHOLDS["block"]:
        return "block"
    if score >= LEVEL_THRESHOLDS["high"]:
        return "high"
    if score >= LEVEL_THRESHOLDS["medium"]:
        return "medium"
    return "low"


def _total_level(scores: dict) -> str:
    """Compute overall risk level from per-dimension scores."""
    if not scores:
        return "LOW"
    max_score = max(scores.values())
    # If any dimension is BLOCK, total is BLOCK
    if max_score >= LEVEL_THRESHOLDS["block"]:
        return "BLOCK"
    if max_score >= LEVEL_THRESHOLDS["high"]:
        return "HIGH"
    if max_score >= LEVEL_THRESHOLDS["medium"]:
        return "MEDIUM"
    return "LOW"


# ═══════════════════════════════════════════════════
# Dimension 1: AI腔风险 (ai_style)
# ═══════════════════════════════════════════════════

_AI_CLICHE_PATTERNS = [
    (r"那一刻[，,]?[^。]{0,20}(终于|忽然|突然)", 0.65),
    (r"她?终于明白[了]?", 0.70),
    (r"她?从未想过", 0.60),
    (r"她?终于意识到", 0.65),
    (r"沉默了几秒", 0.40),
    (r"一切[都]?仿[佛佛]", 0.35),
    (r"由此可见", 0.55),
    (r"这一切说明", 0.55),
    (r"不是.{1,40}而是", 0.55),
    (r"并非.{1,40}而是", 0.55),
    (r"与其说.{1,40}不如说", 0.50),
    (r"综上所述", 0.60),
    (r"然而.{0,15}?她?知道", 0.45),
    (r"他?深吸[一]?口气", 0.30),
    (r"心[里中]暗暗", 0.35),
    (r"夜幕降临", 0.55),
    (r"时光荏苒", 0.55),
    (r"转瞬之间", 0.45),
    (r"在[这那]一刻", 0.30),
    (r"像一(?:座|尊|道)", 0.40),
]


def _score_ai_style(content: str) -> float:
    """Heuristic AI-style detection via pattern matching."""
    try:
        from anti_ai_patterns import run_anti_ai_check
        result = run_anti_ai_check(content)
        if isinstance(result, dict):
            flags = result.get("flags", [])
            issues = result.get("issues", [])
            total_findings = len(flags) + len(issues)
            status = result.get("status", "PASS")
            if status in ("FAIL", "BLOCK", "BLOCKED"):
                return 0.95
            if total_findings == 0:
                return 0.05
            # Score based on finding density
            content_len = max(len(content), 1)
            density = total_findings / (content_len / 500)
            return min(0.95, max(0.05, density * 0.8))
    except ImportError:
        pass

    # Fallback: basic pattern matching
    score = 0.0
    hits = 0
    for pattern, weight in _AI_CLICHE_PATTERNS:
        matches = len(re.findall(pattern, content))
        if matches > 0:
            hits += matches
            score += matches * weight

    content_len = max(len(content), 1)
    density = score / (content_len / 200)
    return min(0.95, max(0.0, density))


# ═══════════════════════════════════════════════════
# Dimension 2: 水文风险 (filler)
# ═══════════════════════════════════════════════════

_FILLER_PATTERNS = [
    (r"(灵气|灵根|灵矿|修炼|境界|功法|丹药|法宝|阵法|符文)", 0.0),
    (r"(也就是说|简单来说|换言之|换句话说|说白了|意味着)", 0.40),
    (r"他(知道|明白|意识到|觉得|感觉|想起)了", 0.25),
    (r"她(知道|明白|意识到|觉得|感觉|想起)了", 0.25),
    (r"总[之的]来说", 0.45),
    (r"概括[起一]?[来下]", 0.40),
    (r"不[得能]不(承认|说)", 0.30),
]


def _score_filler(content: str) -> float:
    """Heuristic filler/padding detection."""
    try:
        from src.guards.padding_guard import run_padding_check
        result = run_padding_check(content)
        if isinstance(result, dict):
            flags = result.get("flags", [])
            score_raw = result.get("padding_score", 0)
            if score_raw > 0:
                return min(0.95, score_raw)
            if flags:
                return min(0.80, len(flags) * 0.15)
            status = result.get("status", "PASS")
            if status == "FAIL":
                return 0.85
            if status == "WARN" or status == "WARNING":
                return 0.50
            return 0.05
    except ImportError:
        pass

    # Fallback: count filler signals
    signal_count = 0
    explanation_signals = re.findall(
        r"(也就是说|简单来说|换言之|换句话说|说白了|意味着)", content
    )
    signal_count += len(explanation_signals)

    settings_in_explanation = 0
    setting_words = re.findall(r"(灵气|灵根|灵矿|修炼|境界|功法|丹药)", content)
    if len(setting_words) > 15 and len(explanation_signals) > 2:
        settings_in_explanation = len(explanation_signals)

    inner_monologue = len(re.findall(
        r"他(知道|明白|意识到|觉得|感觉|想起)了", content
    )) + len(re.findall(
        r"她(知道|明白|意识到|觉得|感觉|想起)了", content
    ))

    total_signals = signal_count + settings_in_explanation + inner_monologue
    content_len = max(len(content), 1)
    density = total_signals / (content_len / 300)
    return min(0.95, max(0.0, density * 0.85))


# ═══════════════════════════════════════════════════
# Dimension 3: 连续性风险 (continuity)
# ═══════════════════════════════════════════════════

def _score_continuity(content: str, chapter_no: int = 0) -> float:
    """Heuristic continuity check."""
    try:
        from src.guards.continuity_evidence_guard import run_continuity_evidence_check
        result = run_continuity_evidence_check(chapter_no, content)
        if isinstance(result, dict):
            flags = result.get("flags", [])
            status = result.get("status", "PASS")
            if status in ("FAIL", "BLOCKED"):
                return 0.90
            if flags:
                return min(0.90, len(flags) * 0.12)
            if status == "WARN" or status == "WARNING":
                return 0.45
            return 0.05
    except ImportError:
        pass

    # Fallback: check for hard state markers not carried forward
    # This is a minimal check since continuity requires prev chapter context
    if chapter_no <= 1:
        return 0.0  # No previous chapter, no continuity risk

    # Check for forgotten-state signals
    injury_mentions = len(re.findall(
        r"(?<!没有)(?<!没)(?<!不)(伤口|流血|骨折|绷带|包扎|伤势)", content
    ))
    # High risk: chapter 2+ has NO mention of previous states
    if injury_mentions == 0 and len(content) > 500:
        return 0.35
    return max(0.0, min(0.70, 0.40 - injury_mentions * 0.10))


# ═══════════════════════════════════════════════════
# Dimension 4: 人设跑偏风险 (character_voice)
# ═══════════════════════════════════════════════════

def _score_character_voice(content: str, chapter_no: int = 0) -> float:
    """Heuristic character voice consistency check."""
    try:
        from src.guards.character_voice_guard import run_character_voice_check
        result = run_character_voice_check(content, chapter_no)
        if isinstance(result, dict):
            flags = result.get("flags", [])
            issues = result.get("issues", [])
            total = len(flags) + len(issues)
            status = result.get("status", "PASS")
            if status in ("FAIL", "BLOCKED"):
                return 0.88
            if total > 0:
                return min(0.88, total * 0.12)
            return 0.03
    except ImportError:
        pass

    # Fallback: basic dialogue/voice pattern check
    # Count dialogue lines
    dialogue_count = len(re.findall(r'[""「『][^""」』]{5,200}[""」』]', content))
    if dialogue_count == 0:
        return 0.0  # No dialogue, no voice risk

    # Check for generic filler dialogue patterns
    filler_dialogue = len(re.findall(
        r'[""「『](?:嗯|哦|啊|好的|知道了|明白)[""」』]', content
    ))
    if filler_dialogue > dialogue_count * 0.5:
        return 0.65

    return min(0.75, filler_dialogue * 0.08)


# ═══════════════════════════════════════════════════
# Dimension 5: 设定幻觉风险 (hallucination)
# ═══════════════════════════════════════════════════

_HALLUCINATION_PATTERNS = [
    (r"(突破|晋升|踏入|进阶).{0,10}(境界|层次|级别|阶段)", 0.65),
    (r"(忽然|突然|竟然).{0,5}(爱上|喜欢上|倾心)", 0.55),
    (r"(从未听过|从未见过|闻所未闻)的(宗门|教派|势力)", 0.75),
    (r"(领悟|掌握|觉醒|获得).{0,10}(新.{0,5}(功法|能力|力量|神通))", 0.60),
    (r"(变成|成为).{1,5}(敌人|仇人|死敌)", 0.50),
    (r"(背叛|出卖|反水)", 0.40),
]


def _score_hallucination(content: str, chapter_no: int = 0) -> float:
    """Heuristic hallucination / setting inconsistency detection."""
    try:
        from src.guards.hallucination_guard import run_hallucination_check
        result = run_hallucination_check(content, chapter_no)
        if isinstance(result, dict):
            flags = result.get("flags", [])
            issues = result.get("issues", [])
            total = len(flags) + len(issues)
            status = result.get("status", "PASS")
            if status in ("FAIL", "BLOCKED"):
                return 0.92
            if total > 0:
                return min(0.92, total * 0.10)
            return 0.02
    except ImportError:
        pass

    # Fallback: pattern matching
    score = 0.0
    for pattern, weight in _HALLUCINATION_PATTERNS:
        matches = len(re.findall(pattern, content))
        if matches > 0:
            score += matches * weight

    return min(0.95, max(0.0, score * 0.85))


# ═══════════════════════════════════════════════════
# Dimension 6: 追读力风险 (reader_pull)
# ═══════════════════════════════════════════════════

_WEAK_OPENING_PATTERNS = [
    r"^(清晨|深夜|清晨的阳光|午后|傍晚)[，,]?",  # Weak time-description opening
    r"^(在|位于|地处)",  # Weak location opening
]

_WEAK_ENDING_PATTERNS = [
    r"他(继续|接着|又).{0,10}(修炼|前进|走着?|等待)$",
    r"一切.{0,10}(恢复|归于).{0,5}(平静|宁静|正常)$",
    r"这[一]?天[就这]?样.{0,10}(过去|结束)了?$",
]

_MID_PRESSURE_PATTERNS = [
    (r"突然.{0,10}(发现|出现|响起|传来)", 0.50),
    (r"(意外|不料|没想到|竟然).{0,10}(发现|出现)", 0.55),
    (r"(危险|威胁|杀意|敌意|压迫)", 0.45),
    (r"(变故|突变|异变|惊变)", 0.50),
]


def _score_reader_pull(content: str) -> float:
    """Heuristic reader pull / engagement check."""
    try:
        from src.guards.reader_pull_guard import run_reader_pull_check
        result = run_reader_pull_check(content)
        if isinstance(result, dict):
            flags = result.get("flags", [])
            status = result.get("status", "PASS")
            pull_score = result.get("reader_pull_score", result.get("pull_score", None))
            if pull_score is not None:
                # pull_score might be 0-100 or 0-1; normalize
                if pull_score > 1:
                    pull_score = pull_score / 100.0
                # Invert: high pull score = low risk
                return max(0.0, min(0.95, 1.0 - pull_score))
            if status == "FAIL":
                return 0.80
            if flags:
                return min(0.80, len(flags) * 0.12)
            return 0.10
    except ImportError:
        pass

    # Fallback: check opening, mid pressure, ending hook
    risk_score = 0.0
    first_para = content[:200] if len(content) > 200 else content

    # Weak opening
    for pat in _WEAK_OPENING_PATTERNS:
        if re.search(pat, first_para):
            risk_score += 0.25
            break

    # Mid-section pressure check (middle third of content)
    third = len(content) // 3
    mid_section = content[third:third * 2]
    pressure_hits = 0
    for pat, weight in _MID_PRESSURE_PATTERNS:
        matches = len(re.findall(pat, mid_section))
        pressure_hits += matches
    if pressure_hits == 0 and len(mid_section) > 300:
        risk_score += 0.30  # No pressure signals in middle

    # Weak ending
    last_para = content[-200:] if len(content) > 200 else content
    for pat in _WEAK_ENDING_PATTERNS:
        if re.search(pat, last_para):
            risk_score += 0.30
            break

    return min(0.95, max(0.0, risk_score))


# ═══════════════════════════════════════════════════
# Dimension 7: 梗出戏风险 (meme)
# ═══════════════════════════════════════════════════

_MEME_PATTERNS = [
    (r"(绝绝子|yyds|栓Q|破防|凡尔赛|躺平|摆烂|内卷|PUA|emo)",
     0.70),
    (r"(牛逼|卧槽|我靠|尼玛|特么)", 0.50),
    (r"(打工人|干饭人|工具人|气氛组)", 0.55),
    (r"(社恐|社牛|社死)", 0.60),
    (r"(芭比Q|芭比q)", 0.70),
    (r"(夺笋|集美|家人们)", 0.55),
    (r"(亿点点|真香|上头|下头)", 0.50),
    (r"(神仙.{0,5}打架|天花板|降维打击)", 0.55),
]


def _score_meme(content: str) -> float:
    """Heuristic meme/internet-slang detection."""
    try:
        from src.guards.character_voice_guard import run_character_voice_check
        result = run_character_voice_check(content, 0)
        if isinstance(result, dict):
            flags = result.get("flags", [])
            # Filter for meme-related flags
            meme_flags = [
                f for f in flags
                if "梗" in str(f.get("message", ""))
                or "meme" in str(f.get("code", "")).lower()
                or "网络" in str(f.get("message", ""))
            ]
            if meme_flags:
                return min(0.92, len(meme_flags) * 0.15)
            # If character voice guard passed, likely low meme risk
            return 0.03
    except ImportError:
        pass

    # Fallback: pattern matching
    score = 0.0
    for pattern, weight in _MEME_PATTERNS:
        matches = len(re.findall(pattern, content))
        if matches > 0:
            score += matches * weight

    return min(0.95, max(0.0, score * 0.90))


# ═══════════════════════════════════════════════════
# Dimension 8: 方言过量风险 (dialect)
# ═══════════════════════════════════════════════════

_DIALECT_TERMS = {
    "sicuan": [
        "啥子", "哪个", "咋个", "晓得", "巴适", "安逸",
        "要得", "不得行", "莫得", "啷个", "耍",
    ],
    "dongbei": [
        "咋地", "嘎哈", "忽悠", "嘚瑟", "杠杠的",
        "贼", "埋汰", "磕碜", "老鼻子", "膈应",
    ],
    "shandong": [
        "俺", "恁", "咋啦", "中不中", "得劲", "不孬",
    ],
    "shaanxi": [
        "谝", "咥", "嫽", "咋咧", "么麻达",
    ],
    "henan": [
        "中", "咋", "弄啥", "得劲", "咦",
    ],
    "shanxi": [
        "甚", "咋", "干甚", "不赖",
    ],
}

_STRONG_DIALECT_PATTERNS = [
    r"俺[们]?",
    r"恁[们]?",
    r"啥[子]?",
    r"咋[了地个咧]?",
    r"咋[个麼]",
    r"啷个",
    r"莫得",
    r"不得行",
    r"要得",
]


def _score_dialect(content: str) -> float:
    """Heuristic dialect overuse detection."""
    try:
        from src.guards.character_voice_guard import run_character_voice_check
        result = run_character_voice_check(content, 0)
        if isinstance(result, dict):
            flags = result.get("flags", [])
            dialect_flags = [
                f for f in flags
                if "方言" in str(f.get("message", ""))
                or "dialect" in str(f.get("code", "")).lower()
                or "dialect" in str(f.get("message", "")).lower()
            ]
            if dialect_flags:
                return min(0.92, len(dialect_flags) * 0.15)
            return 0.03
    except ImportError:
        pass

    # Fallback: count strong dialect terms
    total_dialect_hits = 0
    for pat in _STRONG_DIALECT_PATTERNS:
        matches = len(re.findall(pat, content))
        total_dialect_hits += matches

    # Only flag if density is high
    content_len = max(len(content), 1)
    density = total_dialect_hits / (content_len / 100)

    # Normalize: 1 hit per 100 chars is moderate
    if density < 0.5:
        return 0.0
    if density < 1.0:
        return 0.25
    if density < 2.0:
        return 0.50
    if density < 3.0:
        return 0.75
    return 0.90


# ═══════════════════════════════════════════════════
# RiskScorer class
# ═══════════════════════════════════════════════════

class RiskScorer:
    """Chapter risk scorer with 8 dimensions.

    Usage:
        scorer = RiskScorer(db_path="data/novel_memory.db")
        result = scorer.score_chapter(content, chapter_no=5)
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        # Map dimension names to scoring functions
        self._scorers = {
            "ai_style":       _score_ai_style,
            "filler":         _score_filler,
            "continuity":     _score_continuity,
            "character_voice": _score_character_voice,
            "hallucination":   _score_hallucination,
            "reader_pull":     _score_reader_pull,
            "meme":            _score_meme,
            "dialect":         _score_dialect,
        }

    def score_chapter(
        self,
        content: str,
        chapter_no: int = 0,
        db_path: Optional[str] = None,
    ) -> dict:
        """Score a chapter across all 8 risk dimensions.

        Args:
            content: Chapter text content.
            chapter_no: Chapter number (for continuity context).
            db_path: Override SQLite database path.

        Returns:
            dict with keys:
                - risk_levels: {dim: "low"|"medium"|"high"|"block", ...}
                - risk_scores: {dim: 0.0-1.0, ...}
                - total_risk: "LOW"|"MEDIUM"|"HIGH"|"BLOCK"
                - summary: human-readable summary text
                - blocked: True if total_risk == "BLOCK"
        """
        db = db_path or self.db_path

        scores = {}
        levels = {}

        for dim_name, score_fn in self._scorers.items():
            try:
                if dim_name in ("continuity", "character_voice", "hallucination"):
                    raw_score = score_fn(content, chapter_no)
                else:
                    raw_score = score_fn(content)

                # Clamp to 0.0-1.0
                raw_score = max(0.0, min(1.0, raw_score))
                scores[dim_name] = round(raw_score, 4)
                levels[dim_name] = _score_to_level(raw_score)
            except Exception as e:
                logger.warning(f"Risk dimension '{dim_name}' failed: {e}")
                scores[dim_name] = 0.0
                levels[dim_name] = "low"

        total = _total_level(scores)
        blocked = total == "BLOCK"

        summary = self._build_summary(levels, scores, total)

        return {
            "risk_levels": levels,
            "risk_scores": scores,
            "total_risk": total,
            "summary": summary,
            "blocked": blocked,
        }

    def _build_summary(
        self, levels: dict, scores: dict, total: str
    ) -> str:
        """Build a human-readable Chinese summary."""
        dim_labels = {
            "ai_style": "AI腔",
            "filler": "水文",
            "continuity": "连续性",
            "character_voice": "人设跑偏",
            "hallucination": "设定幻觉",
            "reader_pull": "追读力",
            "meme": "梗出戏",
            "dialect": "方言过量",
        }
        level_labels = {
            "low": "低",
            "medium": "中",
            "high": "高",
            "block": "阻断",
        }

        lines = [f"章节风险评分: {total}"]
        high_dims = []
        block_dims = []

        for dim in RISK_DIMENSIONS:
            lvl = levels.get(dim, "low")
            sc = scores.get(dim, 0.0)
            label = dim_labels.get(dim, dim)
            ll = level_labels.get(lvl, lvl)
            lines.append(f"  [{ll}] {label}: {sc:.2f}")
            if lvl == "block":
                block_dims.append(label)
            elif lvl == "high":
                high_dims.append(label)

        if block_dims:
            lines.append(f"阻断维度: {', '.join(block_dims)}")
        elif high_dims:
            lines.append(f"高风险维度: {', '.join(high_dims)}")
        elif total == "MEDIUM":
            lines.append("存在中等风险，建议审稿时关注。")
        else:
            lines.append("整体风险较低。")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Chapter risk scorer — 8-dimension risk assessment",
    )
    parser.add_argument(
        "content",
        nargs="?",
        help="Path to chapter content file (.txt) or raw text",
    )
    parser.add_argument(
        "--chapter-no", type=int, default=0,
        help="Chapter number for continuity checks",
    )
    parser.add_argument(
        "--db-path", default=None,
        help="SQLite database path",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    if not args.content:
        parser.print_help()
        return 0

    # Load content from file or use as raw text
    content_path = Path(args.content)
    if content_path.exists() and content_path.is_file():
        content = content_path.read_text(encoding="utf-8")
    else:
        content = args.content

    scorer = RiskScorer(db_path=args.db_path)
    result = scorer.score_chapter(content, chapter_no=args.chapter_no)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["summary"])
        print()
        print(f"Total Risk: {result['total_risk']}")
        print(f"Blocked: {result['blocked']}")

    return 1 if result["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main())
