"""schema.py — 统一 Finding schema（Step 0）。

设计原则
========

1. **Finding 描述"问题"，不描述"方案"**
   - 同一个 code 可能对应多种修复（同义替换 / 句式拆分 / 物件注入），
     由 planner 根据上下文决定，不在 schema 里预设。
   - "建议改成具体动作" 这种自然语言保留在 `suggestion` 字段，
     仅供 planner / 人类参考，不是机读的修复指令。

2. **机读 code 必填，message 仅辅助**
   - 现有 detector 输出风格各异（anti_ai 把 code 塞 message 字符串里、
     rhythm_guard 完全没 code），统一在 adapter 层提取/赋码。
   - planner 走规则路由全靠 code，message 只用来生成报告/日志。

3. **位置 optional，但 adapter 应尽力补全**
   - 22 个 detector 中只有 QGP / concrete_anchor 有段/窗口级定位，
     anti_ai 等仅提供 evidence 文本。
   - adapter 拿到 evidence 字符串后，回原文 `text.find(evidence)` 即可
     补全 char_start/char_end，无法精确反查时退化为 paragraph_idx。

4. **不动 detector 现有代码**
   - 所有兼容工作在 src/revision_planner/adapters/ 里完成。
   - 每个 detector 一个 adapter 文件，签名固定。

5. **保留 raw dict 作为兜底**
   - schema 未来扩展字段时，老 adapter 仍可工作。
   - 调试时可看原始 detector 输出。

Severity 命名标准化
==================
- detector 现状: WARN / WARNING / INFO / FAIL / PASS 混用
- 统一映射:
    PASS / OK / NORMAL              → 不产生 Finding（PASS 不是 Finding）
    INFO                            → Severity.INFO
    WARN / WARNING                  → Severity.WARNING
    FAIL / ERROR / CRITICAL         → Severity.ERROR

后续 milestone
==============
- Step 1: adapters/{anti_ai, qgp, style_variation, concrete_anchor, rhythm}.py
- Step 2: planner.py（接受 list[Finding] → list[Action]）
- Step 3: executor.py（Action → 改写文本）
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Severity(str, Enum):
    """Finding 严重度，统一三档。"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# 用于 adapter 把 detector 原 level 标准化到 Severity
SEVERITY_ALIASES: dict[str, Severity] = {
    "info": Severity.INFO,
    "INFO": Severity.INFO,
    "warn": Severity.WARNING,
    "WARN": Severity.WARNING,
    "warning": Severity.WARNING,
    "WARNING": Severity.WARNING,
    "fail": Severity.ERROR,
    "FAIL": Severity.ERROR,
    "error": Severity.ERROR,
    "ERROR": Severity.ERROR,
    "critical": Severity.ERROR,
    "CRITICAL": Severity.ERROR,
}


def normalize_severity(raw: str, *, default: Severity = Severity.WARNING) -> Severity:
    """把 detector 原 level 字符串映射到 Severity。无法识别时返回 default。"""
    if not raw:
        return default
    return SEVERITY_ALIASES.get(raw, SEVERITY_ALIASES.get(raw.upper(), default))


@dataclass(frozen=True)
class TextSpan:
    """文本定位。各字段都是 optional —— adapter 给多少就用多少，
    planner 用时按 char_start/end > paragraph_idx > evidence-only 的优先级降级。

    Attributes:
        paragraph_idx: 0-based 段索引。
        sentence_idx: 段内 0-based 句索引。
        char_start: 全文字符偏移（含）。
        char_end: 全文字符偏移（不含）。
    """
    paragraph_idx: Optional[int] = None
    sentence_idx: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None

    def has_offset(self) -> bool:
        return self.char_start is not None and self.char_end is not None

    def has_paragraph(self) -> bool:
        return self.paragraph_idx is not None


@dataclass
class Finding:
    """detector 报出的一个问题点（adapter 归一化后的统一形态）。

    Attributes:
        source: detector 名称，例如 'prose_agent' / 'perplexity_quality_guard'。
        code: 机读问题代码，例如 'NA_YI_KE' / 'LOW_SURPRISE' / 'OPENING_REPETITION'。
              没有原生 code 的 detector 由 adapter 赋一个稳定字符串。
        severity: 标准化严重度。
        message: 人类可读描述（不要依赖它做规则匹配）。
        evidence: 命中证据，原文片段（≤120 字推荐）。
        location: 位置定位，optional 但建议尽力提供。
        suggestion: detector 给的自然语言修复建议（planner 仅参考）。
        metric: 可选量化指标（例如 ratio / score / count）。
        raw: 原始 detector 字段，调试/兜底用。
    """
    source: str
    code: str
    severity: Severity
    message: str
    evidence: str = ""
    location: Optional[TextSpan] = None
    suggestion: str = ""
    metric: Optional[float] = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """JSON 序列化用。"""
        return {
            "source": self.source,
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "evidence": self.evidence,
            "location": {
                "paragraph_idx": self.location.paragraph_idx,
                "sentence_idx": self.location.sentence_idx,
                "char_start": self.location.char_start,
                "char_end": self.location.char_end,
            } if self.location else None,
            "suggestion": self.suggestion,
            "metric": self.metric,
        }


def locate_in_text(text: str, evidence: str, *, start_pos: int = 0) -> Optional[TextSpan]:
    """工具函数：根据 evidence 在 text 里反查 char_offset。

    Args:
        text: 全文。
        evidence: 要查找的片段。
        start_pos: 从该位置起搜索（用于消歧同一短语的多次出现）。

    策略：先试整段 evidence，再按渐进缩短的前缀（30→20→12→8 字）回退查找，
    避免 evidence 含原文没有的省略/标点造成 false negative。
    多个匹配返回 start_pos 之后的第一个；全部失败返回 None。
    paragraph_idx 用 '\\n\\n' 切段后计算。
    """
    if not evidence or not text:
        return None

    candidates = [evidence] + [evidence[:n].strip() for n in (30, 20, 12, 8)]
    seen: set[str] = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        idx = text.find(cand, start_pos)
        if idx >= 0:
            end = idx + len(cand)
            para_idx = text[:idx].count("\n\n")
            return TextSpan(
                paragraph_idx=para_idx,
                char_start=idx,
                char_end=end,
            )

    return None
