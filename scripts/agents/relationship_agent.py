#!/usr/bin/env python3
"""relationship_agent.py — 人物关系 Agent v0.6.5

检查人物关系是否有变化: 升温/降温/误会/信任/人情债等。
"""
import re
from .base_agent import BaseAgent

# 关系变化标记
RELATIONSHIP_CHANGE = [
    re.compile(r'(信任|信赖|相信|放心)'),  # 信任增加
    re.compile(r'(怀疑|猜疑|不信|试探|提防|防备)'),  # 信任减少
    re.compile(r'(感谢|感激|感恩|感动|欠|情|恩情|人情)'),  # 人情债
    re.compile(r'(误会|误解|错怪|冤枉|委屈)'),  # 误会
    re.compile(r'(道歉|认错|赔罪|低头|服软)'),  # 关系修复
    re.compile(r'(疏远|冷淡|避开|绕开|不再|陌生)'),  # 关系降温
    re.compile(r'(靠拢|接近|拉近|走近|贴[近了])'),  # 关系升温
    re.compile(r'(利用|算计|坑|害|骗|耍|戏[弄耍])'),  # 利益关系
    re.compile(r'(授|传|教|指点|引导|提携|提拔)'),  # 师徒/上下级
    re.compile(r'(承诺|答应|约定|保证|发誓|绝不)'),  # 承诺
]

# 配角只服务主角
SIDEKICK_PATTERNS = [
    re.compile(r'(^[^。]{0,10}(小五|马瘸子|顾长庚|韩烈|吴执事|赵管事|老杂役).{0,10}(帮|替|为|给|帮|替|为|给)[^，。]{5,30})'),
]

class RelationshipAgent(BaseAgent):
    """人物关系审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="relationship", config=config)
        self.min_changes = self.config.get("min_changes", 3)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 55

        # 关系变化检测
        change_count = 0
        change_types = set()
        for pat in RELATIONSHIP_CHANGE:
            matches = pat.findall(content)
            if matches:
                change_count += len(matches)
                change_types.add(pat.pattern[:20])

        types_count = len(change_types)

        if change_count < self.min_changes:
            findings.append(self._make_finding(
                "WARN", f"人物关系无变化: 仅{change_count}处关系信号",
                suggestion="每章至少让一对人物关系有微小变化: 多一分信任、少一分怀疑、欠一个人情"))
            score -= 20
        elif types_count >= 3:
            score += 10

        if types_count == 1 and change_count > 0:
            findings.append(self._make_finding(
                "WARN", f"人物关系单一: 只有1种关系变化重复出现",
                suggestion="丰富关系维度: 信任、人情、误会、利益、承诺交替出现"))
            score -= 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._build_result(score, status, findings)
