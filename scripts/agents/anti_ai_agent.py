#!/usr/bin/env python3
"""
anti_ai_agent.py — 反AI腔Agent v0.5.5

检查:
  1. AI句式 — "不是A而是B", "并非...而是" 等
  2. AI套话 — "那一刻终于明白", "从未想过", "沉默了几秒" 等
  3. 硬科普腔 — 修仙文中出现科学术语
  4. 模板句/水文 — 空泛总结句、凑字段落
  5. 水文密度 — 单段信息密度过低

策略: 复用 anti_ai_patterns.py 的模式库, 增加水文检测
"""

import re
from .base_agent import BaseAgent

# ── AI句式 (复用 anti_ai_patterns) ──
NOT_A_B_PATTERNS = [
    (re.compile(r"不是.{1,40}而是"), "NOT_A_ER_SHI"),
    (re.compile(r"并非.{1,40}而是"), "BING_FEI_A_ER_SHI"),
    (re.compile(r"与其说.{1,40}不如说"), "YU_QI_SHUO"),
]

# ── AI套话 ──
AI_CLICHE_PATTERNS = [
    (re.compile(r"那一刻[，,]?[^。]{0,20}(终于|忽然|突然)"), "NA_YI_KE"),
    (re.compile(r"(终于明白|终于意识到|终于懂了|终于看清)"), "ZHONG_YU_MING_BAI"),
    (re.compile(r"(从未想过|从未见过|从未感受过)"), "CONG_WEI_XIANG_GUO"),
    (re.compile(r"沉默了几秒"), "CHEN_MO_JI_MIAO"),
    (re.compile(r"像一座(废墟|孤岛|坟墓)"), "XIANG_FEI_XU"),
    (re.compile(r"是她的救赎"), "SHI_JIU_SHU"),
    (re.compile(r"像一尊(雕像|雕塑|石像)"), "XIANG_DIAO_XIANG"),
    (re.compile(r"心中.{1,15}(涌起|升起|泛起).{1,10}(暖流|寒意|不安|恐惧)"), "XIN_ZHONG_YONG_QI"),
    (re.compile(r"深吸一口气"), "SHEN_XI_YI_KOU_QI"),
    (re.compile(r"眼神中.{1,15}(闪过一丝|掠过一抹|透出)"), "YAN_SHEN_SHI"),
    # v0.5.5 新增：总结腔/水文模板
    (re.compile(r"(总而言之|综上所述|总的来说|不管怎样|无论如何)"), "ZONG_JIE_QIANG"),
    (re.compile(r"(这.{1,5}就是.{1,6}的全部意义|这就是.{1,4}的真相)"), "MO_BAN_DING_YI"),
]

# ── 硬科普检测 ──
HARD_SCIENCE_PATTERNS = [
    (re.compile(r"根据.{1,20}(方程|公式|定理|定律)"), "HARD_SCIENCE_REF"),
    (re.compile(r"(傅里叶|拓扑|微分方程|偏转方程|量子态|波函数|哈密顿|DNA|基因|纳米|量子|粒子|质子|中子|电子)"), "HARD_SCIENCE_TERM"),
    (re.compile(r"(概率.{1,10}(百分之|%))"), "PROBABILITY_PCT"),
]

# ── 水文/凑字段落检测 ──
# 一段文字中有效信息密度 < 阈值
WATER_CONTENT_PATTERNS = [
    re.compile(r'(他|她)(看|望|盯|瞅)(了|着).{0,15}(一眼|一下)'),  # 过多的"看了一眼"
    re.compile(r'(说|道|问|答|叫|喊)(了一句|了一声)'),  # 缺少具体描述
    re.compile(r'(.{0,30})(又|再次|重新)(.{0,30})'),  # 无意义的重复前缀
]

# ── 物理证据关键词 (降低误报) ──
EVIDENCE_KEYWORDS = [
    "水缸", "柴刀", "石", "矿", "碗", "树皮", "木牌", "役牌",
    "青苔", "止血丸", "油纸", "草鞋", "炭笔", "馒头", "粥",
    "劈", "砍", "推", "搬", "抬", "抓", "按", "压", "砸",
    "裂开", "渗血", "破皮", "流鼻血", "肿包",
]


class AntiAIAgent(BaseAgent):
    """反AI腔/模板句审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="anti_ai_agent", config=config)
        self.max_not_a_b = self.config.get("max_not_a_b", 3)
        self.max_cliches = self.config.get("max_cliches", 1)
        self.min_paragraph_info = self.config.get("min_paragraph_info", 30)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        total_weight = 0

        # ── 1. "不是A而是B" 检测 ──
        not_a_b_count = 0
        for pat, code in NOT_A_B_PATTERNS:
            for m in pat.finditer(content):
                snippet = content[max(0, m.start()-20):m.end()+60].replace('\n', ' ')
                has_evidence = any(kw in snippet for kw in EVIDENCE_KEYWORDS)
                weight = 0.5 if has_evidence else 1.0
                if not has_evidence or not_a_b_count > self.max_not_a_b:
                    findings.append(self._make_finding(
                        "WARN", f"AI句式 [{code}]: '{m.group()[:40]}'",
                        evidence=snippet[:120],
                        suggestion="改为具体动作/对话推进, 或加入物理证据降低AI感"))
                    not_a_b_count += 1
                    total_weight += 20 * weight

        if not_a_b_count >= 4:
            findings.append(self._make_finding(
                "WARN", f"AI句式泛滥: 本章共{not_a_b_count}处'不是而是'类",
                suggestion="大幅减少此类句式, 每章建议≤3处"))
            total_weight += 15

        # ── 2. AI套话检测 ──
        cliche_count = 0
        for pat, code in AI_CLICHE_PATTERNS:
            for m in pat.finditer(content):
                snippet = content[max(0, m.start()-10):m.end()+40].replace('\n', ' ')
                findings.append(self._make_finding(
                    "WARN", f"AI套话 [{code}]: '{m.group()[:50]}'",
                    evidence=snippet[:120],
                    suggestion="替换为具体行为/感受描写"))
                cliche_count += 1
                total_weight += 25

        if cliche_count >= 3:
            findings.append(self._make_finding(
                "WARN", f"AI套话过多: {cliche_count}处",
                suggestion="AI套话是编辑最敏感的标志, 每章应≤1处"))

        # ── 3. 硬科普检测 ──
        for pat, code in HARD_SCIENCE_PATTERNS:
            for m in pat.finditer(content):
                findings.append(self._make_finding(
                    "WARN", f"硬科普 [{code}]: '{m.group()[:40]}'",
                    evidence=content[max(0, m.start()-20):m.end()+40].replace('\n', ' ')[:120],
                    suggestion="修仙文中避免使用现代科学术语"))
                total_weight += 15

        # ── 4. 水文/凑字检测 ──
        paragraphs = self._get_paragraphs(content)
        water_paras = 0
        for i, para in enumerate(paragraphs):
            chinese = self._count_chinese(para)
            if chinese < self.min_paragraph_info and chinese > 5:
                # 太短但非空
                continue
            if chinese > 80:
                # 检查 "看了一眼" 密度
                look_count = len(re.findall(r'看了.{0,5}一眼', para))
                if look_count >= 3:
                    findings.append(self._make_finding(
                        "WARN", f"水文段落: 含{look_count}次'看了...一眼'",
                        evidence=para[:80],
                        suggestion="压缩重复动作, 合并为一次具体描写"))
                    water_paras += 1
                    total_weight += 10

                say_count = len(re.findall(r'(说|道|问)(了一句|了一声)', para))
                if say_count >= 2 and chinese < 200:
                    findings.append(self._make_finding(
                        "WARN", f"对话标记重复: {say_count}次'说了一句/道了一声'",
                        evidence=para[:80],
                        suggestion="对话标记应多样化, 或省略标记直接展示对白"))
                    total_weight += 8

        # ── 5. 总结腔检测 ──
        summary_re = re.compile(r'(总而言之|综上所述|总的来说|不管怎样|无论如何|这就意味着|也就是说)')
        summary_matches = summary_re.findall(content)
        if len(summary_matches) >= 2:
            findings.append(self._make_finding(
                "WARN", f"总结腔/说教腔: {len(summary_matches)}处",
                evidence=', '.join(summary_matches[:5]),
                suggestion="叙事中用情节自然展现道理, 不要替读者总结"))
            total_weight += 20

        # ── 裁决 ──
        score = min(100, total_weight)
        if score == 0:
            status = "PASS"
        elif score <= 30:
            status = "WARNING"
        elif score <= 60:
            status = "WARNING"
        else:
            status = "WARNING"

        return self._build_result(score, status, findings)
