#!/usr/bin/env python3
"""paragraph_texture_agent.py — 段落质感 Agent v0.6.5

检查段落是否过于整齐、像AI: 长度平均、句式单一、连接词堆砌。
"""
import re
from .base_agent import BaseAgent

# 句式单一检测
SENTENCE_STARTERS = [
    (re.compile(r'^(他|她|它|林观澜|韩烈)'), '主语开头'),
    (re.compile(r'^(但|可|然而|不过|却|而)'), '转折开头'),
    (re.compile(r'^(这|那|此)'), '指示词开头'),
    (re.compile(r'^(在|当|随[着]|经[过]|通[过]|根据)'), '介词开头'),
]

# 连接词堆砌
TRANSITION_WORDS = [
    re.compile(r'(然而|事实上|与此同时|这意味着|换句话说|总而言之|总之)'),
    re.compile(r'(此外|另外|不仅如此|更重要的[是])'),
]

class ParagraphTextureAgent(BaseAgent):
    """段落质感审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="paragraph_texture", config=config)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 60

        # 1. 段落长度均匀度检测
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        para_lengths = [len(p) for p in paragraphs if len(p) > 10]

        if len(para_lengths) >= 5:
            avg_len = sum(para_lengths) / len(para_lengths)
            # 检查是否太多段落接近平均长度
            near_avg = sum(1 for l in para_lengths if abs(l - avg_len) < avg_len * 0.3)
            uniformity = near_avg / len(para_lengths)

            if uniformity > 0.7:
                findings.append(self._make_finding(
                    "WARN", f"段落过于均匀: {uniformity:.0%}段落长度相近",
                    suggestion="变换段落长度，长短句交替，打破整齐感"))

        # 2. 连接词堆砌
        transition_count = 0
        for pat in TRANSITION_WORDS:
            transition_count += len(pat.findall(content))

        total_chars = max(len(content), 1)
        transition_per_k = transition_count * 1000 / total_chars
        if transition_per_k > 3:
            findings.append(self._make_finding(
                "WARN", f"连接词堆砌({transition_per_k:.1f}/千字): '然而/事实上/此外/与此同时'",
                suggestion="删掉多余的连接词，用空行和动作自然过渡"))
            score -= 20

        # 3. 句式多样性
        starter_counts = {}
        sentences = re.split(r'[。！？]', content)[:30]  # 检查前30句
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            for pat, label in SENTENCE_STARTERS:
                if pat.match(s):
                    starter_counts[label] = starter_counts.get(label, 0) + 1
                    break

        max_starter = max(starter_counts.values()) if starter_counts else 0
        if max_starter > len(sentences) * 0.5 and len(sentences) > 10:
            dominant = max(starter_counts, key=starter_counts.get)
            findings.append(self._make_finding(
                "WARN", f"句式单一: {dominant}占比>{max_starter/len(sentences):.0%}",
                suggestion="打破'主语+谓语'惯性，混合动作句/感官句/对话句"))

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._build_result(score, status, findings)
