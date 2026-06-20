"""text_metrics.py — 共享文本统计指标 v1.0

为多个 guard 提供单一真值的统计 helper，消除句长 CV 与
重复短语比例的重复实现（dialogue_naturalness_guard /
dialogue_structure_guard / perplexity_quality_guard 共用）。
"""

from __future__ import annotations
import re
import statistics
from collections import Counter
from typing import Iterable


def length_cv(values: Iterable[float]) -> float:
    """计算变异系数 CV = std / mean，对长度序列输出 0-∞ 浮点数。

    少于 2 个样本返回 0.0。mean=0 时返回 0.0。
    """
    lst = list(values)
    if len(lst) < 2:
        return 0.0
    mean_val = statistics.mean(lst)
    if mean_val <= 0:
        return 0.0
    std_val = statistics.stdev(lst)
    return round(std_val / mean_val, 3)


def repeated_phrase_ratio(text: str, min_len: int = 4, max_len: int = 8) -> float:
    """检测重复短语比例（min_len~max_len 长度的中文子串），返回 0.0-1.0。

    出现 >= 3 次的短语数量 / 不同短语数量。
    """
    chinese_only = ''.join(c for c in text if '一' <= c <= '鿿')
    if len(chinese_only) < min_len * 2:
        return 0.0

    phrases: Counter = Counter()
    total_phrases = 0
    for L in range(min_len, max_len + 1):
        for i in range(len(chinese_only) - L + 1):
            phrase = chinese_only[i:i + L]
            phrases[phrase] += 1
            total_phrases += 1

    if total_phrases == 0:
        return 0.0
    repeated = sum(1 for c in phrases.values() if c >= 3)
    return round(min(1.0, repeated / max(len(phrases), 1)), 3)
