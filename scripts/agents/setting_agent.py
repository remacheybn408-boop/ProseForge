#!/usr/bin/env python3
"""
setting_agent.py — 修仙设定自洽Agent v0.5.5

检查:
  1. 修仙设定自洽 — 境界体系/灵力规则/功法体系是否前后一致
  2. 物理类比 — 修仙世界是否出现不当的现代物理类比
  3. 前后矛盾规则 — 同一规则是否在不同章节有矛盾描述
  4. 物品设定 — 法宝/丹药/材料的名称和功能是否一致
  5. 世界观规则 — 社会结构/经济/宗门规则是否逻辑自洽

策略: 基于关键词和规则库做逻辑检查
"""

import re
from .base_agent import BaseAgent

# ── 修仙境界体系 ──
REALM_HIERARCHY = {
    "炼气": 1, "筑基": 2, "金丹": 3, "元婴": 4,
    "化神": 5, "炼虚": 6, "合体": 7, "大乘": 8, "渡劫": 9,
    "人仙": 10, "地仙": 11, "天仙": 12, "金仙": 13,
    "太乙": 14, "大罗": 15, "混元": 16,
}

# ── 物理类比 (修仙文中应避免) ──
PHYSICS_ANALOGY_PATTERNS = [
    (re.compile(r'(如同|就像|好比|仿佛).{1,20}(电流|电压|电路|电子|磁场|电场)'), "电磁类比"),
    (re.compile(r'(如同|就像|好比|仿佛).{1,20}(程序|代码|系统|算法|字节|数据)'), "计算机类比"),
    (re.compile(r'(如同|就像|好比|仿佛).{1,20}(基因|DNA|细胞|染色体|进化论)'), "生物类比"),
    (re.compile(r'(如同|就像|好比|仿佛).{1,20}(分子|原子|粒子|量子|纳米)'), "物理类比"),
    (re.compile(r'(如同|就像|好比|仿佛).{1,20}(引擎|马达|齿轮|机器|机械)'), "机械类比"),
    (re.compile(r'(如同|就像|好比|仿佛).{1,20}(数学|公式|方程|函数|算法)'), "数学类比"),
    (re.compile(r'(百分之|%|百分比)'), "百分比表达"),
]

# ── 境界矛盾检查 ──
REALM_CONTRADICTION_PATTERNS = [
    # 境界设定前后矛盾: 低境界击败高境界需要解释
    re.compile(r'(炼气).{0,30}(击败|斩杀|秒杀).{0,30}(金丹|元婴|化神)'),
    re.compile(r'(筑基).{0,30}(击败|斩杀|秒杀).{0,30}(元婴|化神|炼虚)'),
]

# ── 规则矛盾 ──
RULE_CONTRADICTION_MARKERS = [
    (re.compile(r'(?<!不)能.{1,15}(?<!不)能'), "能...能 冗余"),
    (re.compile(r'(必需|必须).{1,30}(但也|但也可能|但也不是|但也不)'), "规则摇摆"),
    (re.compile(r'(只有|唯有|唯一的).{1,40}(但是|然而|不过|却)'), "规则例外过多"),
]

# ── 丹药/物品名不一致 ──
ITEM_ALIAS_PATTERNS = [
    (re.compile(r'筑基丹'), ['筑基丹', '筑基丸', '筑基药']),
    (re.compile(r'凝气丹'), ['凝气丹', '聚气丹', '凝气丸']),
    (re.compile(r'止血丸'), ['止血丸', '止血丹']),
]

# ── 灵石/货币 ──
CURRENCY_PATTERNS = re.compile(
    r'(\d+)(枚|颗|块|两|贯)?\s*(灵石|下品灵石|中品灵石|上品灵石|极品灵石|'
    r'灵晶|灵币|金币|银币|铜币|银两|黄金)')
# 检测是否有同时用两种货币系统
DUAL_CURRENCY_PAIRS = [
    (["灵石", "灵晶", "灵币"], ["金币", "银币", "铜币", "银两", "黄金"]),
]


class SettingAgent(BaseAgent):
    """修仙设定自洽审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="setting_agent", config=config)
        self.strict_physics = self.config.get("strict_physics", True)
        self.strict_realm = self.config.get("strict_realm", True)
        self.allow_cross_realm = self.config.get("allow_cross_realm", False)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        issues_weight = 0

        # ── 1. 物理类比检测 ──
        physics_issues = []
        for pat, category in PHYSICS_ANALOGY_PATTERNS:
            matches = pat.findall(content)
            if matches:
                for m in matches[:3]:
                    physics_issues.append(f"{category}: '{m[:40] if isinstance(m, str) else str(m[:40])}'")
                issues_weight += len(matches) * 20

        if physics_issues:
            findings.append(self._make_finding(
                "WARN", f"不当物理类比: {len(physics_issues)}处",
                evidence="; ".join(physics_issues[:3]),
                suggestion="修仙文的比喻应取自自然/器物, 避免现代科学类比"))

        # ── 2. 境界矛盾检测 ──
        if not self.allow_cross_realm:
            realm_issues = []
            for pat in REALM_CONTRADICTION_PATTERNS:
                matches = pat.findall(content)
                if matches and isinstance(matches[0], tuple):
                    for m in matches[:2]:
                        realm_issues.append(
                            f"{m[0]}击败{m[2] if len(m) > 2 else m[1]}")
                elif matches:
                    realm_issues.extend(str(m)[:40] for m in matches[:2])

            if realm_issues and not any(
                w in content for w in ['越级', '跨境', '跨境界',
                                        '出其不意', '偷袭', '法宝', '秘术',
                                        '自爆', '燃烧', '耗尽了']):
                findings.append(self._make_finding(
                    "WARN", "境界矛盾: 低境界无解释击败高境界",
                    evidence="; ".join(realm_issues[:3]),
                    suggestion="跨境战斗需明确解释: 法宝/偷袭/秘术/对方虚弱等"))
                issues_weight += 25

        # ── 3. 规则摇摆检测 ──
        for pat, label in RULE_CONTRADICTION_MARKERS:
            matches = pat.findall(content)
            if len(matches) >= 2:
                findings.append(self._make_finding(
                    "WARN", f"规则摇摆 ({label}): {len(matches)}处",
                    evidence=str(matches[:3])[:100],
                    suggestion="世界观规则应明确坚定, 避免'可以但也不可以'式摇摆"))
                issues_weight += 15

        # ── 4. 丹药/物品别名检查 ──
        for pat, aliases in ITEM_ALIAS_PATTERNS:
            found = []
            for alias in aliases:
                if alias in content:
                    found.append(alias)
            if len(found) >= 2:
                findings.append(self._make_finding(
                    "WARN", f"物品别名混用: {', '.join(found)}",
                    suggestion=f"统一使用一个名称, 推荐'{aliases[0]}'"))
                issues_weight += 10

        # ── 5. 货币系统 ──
        currency_matches = CURRENCY_PATTERNS.findall(content)
        currency_systems = set()
        for m in currency_matches:
            ctype = m[3] if len(m) > 3 else ""
            currency_systems.add(ctype)

        for sys_a, sys_b in DUAL_CURRENCY_PAIRS:
            has_a = any(cs in sys_a for cs in currency_systems)
            has_b = any(cs in sys_b for cs in currency_systems)
            if has_a and has_b:
                findings.append(self._make_finding(
                    "WARN", "双货币系统混用",
                    evidence=f"同时出现修仙货币({[c for c in currency_systems if c in sys_a]}) "
                             f"和凡间货币({[c for c in currency_systems if c in sys_b]})",
                    suggestion="确认世界观是否需要双货币系统, 或统一为单一系统"))
                issues_weight += 10
                break

        # ── 6. 修仙常识矛盾 ──
        # 灵气=灵力来源, 不能同时说"灵气稀薄"又说"灵力充沛"
        if "灵气" in content and "灵力" in content:
            thin = re.findall(r'(稀薄|稀|少|匮乏|枯竭)', content)
            rich = re.findall(r'(充沛|充裕|丰富|浓郁|浑厚)', content)
            if thin and rich:
                findings.append(self._make_finding(
                    "WARN", "灵气/灵力描述矛盾",
                    evidence=f"灵气: {thin[:2]}, 灵力: {rich[:2]}",
                    suggestion="灵力源于灵气, 两者状态应一致"))

        # ── 7. 宗门规则 ──
        # 杂役/外门/内门/核心/长老 等级不跳
        sect_ranks = re.findall(r'(杂役|外门|内门|核心|亲传|长老|掌门|太上)', content)
        unique_ranks = list(set(sect_ranks))
        # 检查是否合理 (不做硬性检查, 仅记录)
        pass

        # ── 裁决 ──
        score = min(100, issues_weight)
        if score == 0:
            status = "PASS"
        elif score <= 40:
            status = "WARNING"
        else:
            status = "WARNING"

        return self._build_result(score, status, findings)
