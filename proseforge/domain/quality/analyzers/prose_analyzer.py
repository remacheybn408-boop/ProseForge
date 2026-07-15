#!/usr/bin/env python3
"""Merged prose agent."""

import re

from .base_analyzer import BaseAnalyzer


NOT_A_B_PATTERNS = [
    (re.compile(r"不是.{1,40}而是"), "NOT_A_ER_SHI"),
    (re.compile(r"并非.{1,40}而是"), "BING_FEI_A_ER_SHI"),
    (re.compile(r"与其说.{1,40}不如说"), "YU_QI_SHUO"),
]
AI_CLICHE_PATTERNS = [
    (re.compile(r"那一刻[，,]?[^。！？\n]{0,20}(终于|忽然|突然)"), "NA_YI_KE"),
    (re.compile(r"(终于明白|终于意识到|终于懂了|终于看清)"), "ZHONG_YU_MING_BAI"),
    (re.compile(r"(从未想过|从未见过|从未感受过)"), "CONG_WEI_XIANG_GUO"),
    (re.compile(r"沉默了几秒"), "CHEN_MO_JI_MIAO"),
    (re.compile(r"像一座?(废墟|孤岛|坟墓)"), "XIANG_FEI_XU"),
    (re.compile(r"是她的救赎"), "SHI_JIU_SHU"),
    (re.compile(r"像一尊?(雕像|雕塑|石像)"), "XIANG_DIAO_XIANG"),
    (re.compile(r"心中.{1,15}(涌起|升起|泛起).{1,10}(暖流|寒意|不安|恐惧)"), "XIN_ZHONG_YONG_QI"),
    (re.compile(r"深吸一口气"), "SHEN_XI_YI_KOU_QI"),
    (re.compile(r"眼神中?.{1,15}(闪过一丝|掠过一抹|透出)"), "YAN_SHEN_SHI"),
    (re.compile(r"(总而言之|综上所述|总的来说|不管怎么样|无论如何)"), "ZONG_JIE_QIANG"),
    (re.compile(r"(这.{1,5}就是.{1,6}的全部意义|这就是.{1,4}的真相)"), "MO_BAN_DING_YI"),
]
HARD_SCIENCE_PATTERNS = [
    (re.compile(r"根据.{1,20}(方程|公式|定理|定律)"), "HARD_SCIENCE_REF"),
    (re.compile(r"(傅里叶|拓扑|微分方程|偏转方程|量子态|波函数|DNA|基因|纳米|量子|粒子|质子|中子|电子)"), "HARD_SCIENCE_TERM"),
    (re.compile(r"(概率.{1,10}(百分之|%))"), "PROBABILITY_PCT"),
]
EVIDENCE_KEYWORDS = [
    "水缸", "柴刀", "石头", "树皮", "木牌", "腰牌", "青苔", "止血丹", "草鞋", "馒头",
    "抓", "砸", "推", "搬", "扛", "破", "裂开", "渗血", "破皮", "流鼻血", "肿包",
]
SENTENCE_STARTERS = [
    (re.compile(r"^(他|她|它)"), "主语开头"),
    (re.compile(r"^(但|可是|然而|不过|却|而)"), "转折开头"),
    (re.compile(r"^(这|那|此)"), "指示词开头"),
    (re.compile(r"^(在|当|随着|经由|通过|根据)"), "介词开头"),
]
TRANSITION_WORDS = [
    re.compile(r"(然而|事实上|与此同时|这意味着|换句话说|总而言之|总之)"),
    re.compile(r"(此外|另外|不仅如此|更重要的是)"),
]
EXPLICIT_EXPLAIN = [
    re.compile(r"(因为.{1,20}所以)"),
    re.compile(r"(其实.{1,30}(是因为))"),
    re.compile(r"(我(?:就|才)?是因为.{1,20})"),
    re.compile(r"(你应该知道.{1,20}(因为))"),
    re.compile(r"(坦白说|老实说|说白了|说实话|不瞒你说)"),
    re.compile(r"(我[^，。！？\n]{0,10}(在乎|关心|担心|害怕|喜欢|讨厌)[^，。！？\n]{0,20}[你我他她它们])"),
]
SUBTEXT_GOOD = [
    re.compile(r"(冷笑|哼|嗤|呵)"),
    re.compile(r"(别过[脸头]|偏过[头脸]|不看|避开|垂下眼睫)"),
    re.compile(r"(顿了一顿|停了一下|沉默了|没说话)"),
    re.compile(r"(随便|无所谓|你定|都行|算了|没事)"),
]
REALM_CONTRADICTION_PATTERNS = [
    re.compile(r"(炼气).{0,30}(击败|斩杀|秒杀).{0,30}(金丹|元婴|化神)"),
    re.compile(r"(筑基).{0,30}(击败|斩杀|秒杀).{0,30}(元婴|化神|炼虚)"),
]
PHYSICS_ANALOGY_PATTERNS = [
    (re.compile(r"(如同|就像|好比|仿佛).{1,20}(电流|电压|电路|电子|磁场|电场)"), "电磁类比"),
    (re.compile(r"(如同|就像|好比|仿佛).{1,20}(程序|代码|系统|算法|字节|数据)"), "计算机类比"),
    (re.compile(r"(如同|就像|好比|仿佛).{1,20}(基因|DNA|细胞|染色体|进化论)"), "生物类比"),
    (re.compile(r"(如同|就像|好比|仿佛).{1,20}(分子|原子|粒子|量子|纳米)"), "物理类比"),
    (re.compile(r"(如同|就像|好比|仿佛).{1,20}(引擎|马达|齿轮|机器|机械)"), "机械类比"),
    (re.compile(r"(百分之|%)"), "百分比表达"),
]
RULE_CONTRADICTION_MARKERS = [
    (re.compile(r"(?<!不)能.{1,15}(?<!不)能"), "能..能重复"),
    (re.compile(r"(必须|必需).{1,30}(但也|但也可能|但也不是|但也不)"), "规则摇摆"),
    (re.compile(r"(只有|唯有|唯一的).{1,40}(但是|然而|不过|却)"), "规则例外过多"),
]
ITEM_ALIAS_PATTERNS = [
    (re.compile(r"筑基丹"), ["筑基丹", "筑基药", "筑基灵药"]),
    (re.compile(r"凝气丹"), ["凝气丹", "聚气丹", "凝灵丹"]),
    (re.compile(r"止血丹"), ["止血丹", "止血丸"]),
]
DUAL_CURRENCY_PAIRS = [
    (["灵石", "灵晶", "灵币"], ["金币", "银币", "铜币", "银两", "黄金"]),
]
CURRENCY_PATTERNS = re.compile(
    r"(\d+)(枚|颗|块|两|贯)?\s*(灵石|下品灵石|中品灵石|上品灵石|极品灵石|灵晶|灵币|金币|银币|铜币|银两|黄金)"
)


class ProseAnalyzer(BaseAnalyzer):
    """Merged prose/style/setting agent."""

    def __init__(self, config: dict = None):
        super().__init__(name="prose_agent", config=config)
        self.max_not_a_b = self.config.get("max_not_a_b", 3)
        self.max_cliches = self.config.get("max_cliches", 1)
        self.min_paragraph_info = self.config.get("min_paragraph_info", 30)
        self.max_explicit = self.config.get("max_explicit", 5)
        self.min_subtext = self.config.get("min_subtext", 3)

    def review(self, content: str, chapter_no: int = 0, context: dict = None) -> dict:
        components = [
            self._review_anti_ai(content),
            self._review_paragraph_texture(content),
            self._review_subtext(content),
            self._review_setting(content),
        ]
        return self._merge_components(components)

    def _review_anti_ai(self, content: str) -> dict:
        findings = []
        total_weight = 0
        not_a_b_count = 0

        for pattern, code in NOT_A_B_PATTERNS:
            for match in pattern.finditer(content):
                snippet = content[max(0, match.start() - 20):match.end() + 60].replace("\n", " ")
                has_evidence = any(keyword in snippet for keyword in EVIDENCE_KEYWORDS)
                weight = 0.5 if has_evidence else 1.0
                if (not has_evidence) or not_a_b_count > self.max_not_a_b:
                    findings.append(
                        self._make_finding(
                            "WARN",
                            f"AI句式 [{code}]: '{match.group()[:40]}'",
                            evidence=snippet[:120],
                            suggestion="改为具体动作/对白推进，或加入物理证据降位AI感",
                        )
                    )
                    not_a_b_count += 1
                    total_weight += int(20 * weight)

        if not_a_b_count >= 4:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"AI句式泛滥: 本章共{not_a_b_count}处'不是而是'类",
                    suggestion="大幅减少此类句式，每章建议≤3处",
                )
            )
            total_weight += 15

        cliche_count = 0
        for pattern, code in AI_CLICHE_PATTERNS:
            for match in pattern.finditer(content):
                snippet = content[max(0, match.start() - 10):match.end() + 40].replace("\n", " ")
                findings.append(
                    self._make_finding(
                        "WARN",
                        f"AI套话 [{code}]: '{match.group()[:50]}'",
                        evidence=snippet[:120],
                        suggestion="替换为具体行动、感受或场面",
                    )
                )
                cliche_count += 1
                total_weight += 25

        if cliche_count >= 3:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"AI套话过多: {cliche_count}处",
                    suggestion="AI套话是编辑最敏感的标记，每章应尽量压到1处以内",
                )
            )

        for pattern, code in HARD_SCIENCE_PATTERNS:
            for match in pattern.finditer(content):
                findings.append(
                    self._make_finding(
                        "WARN",
                        f"硬科普 [{code}]: '{match.group()[:40]}'",
                        evidence=content[max(0, match.start() - 20):match.end() + 40].replace("\n", " ")[:120],
                        suggestion="正文中避免现代科学术语",
                    )
                )
                total_weight += 15

        paragraphs = self._get_paragraphs(content)
        for para in paragraphs:
            chinese = self._count_chinese(para)
            if chinese < self.min_paragraph_info and chinese > 5:
                continue
            if chinese > 80:
                look_count = len(re.findall(r"看了.{0,5}一眼", para))
                if look_count >= 3:
                    findings.append(
                        self._make_finding(
                            "WARN",
                            f"水文段落: 含{look_count}次'看了...一眼'",
                            evidence=para[:80],
                            suggestion="压缩重复动作，合并为一次更具体的描写",
                        )
                    )
                    total_weight += 10

                say_count = len(re.findall(r"(说|道|问)(了一句|了一声)", para))
                if say_count >= 2 and chinese < 200:
                    findings.append(
                        self._make_finding(
                            "WARN",
                            f"对话标记重复: {say_count}次'说了一句/道了一声'",
                            evidence=para[:80],
                            suggestion="对话标记应多样化，或省略标记直接展示对白",
                        )
                    )
                    total_weight += 8

        summary_matches = re.findall(r"(总而言之|综上所述|总的来说|不管怎么样|无论如何|这就意味着|也就是说)", content)
        if len(summary_matches) >= 2:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"总结腔/说教腔: {len(summary_matches)}处",
                    evidence=", ".join(summary_matches[:5]),
                    suggestion="用情节自然展示意义，不要替读者总结",
                )
            )
            total_weight += 20

        status = "PASS" if total_weight == 0 else "WARNING"
        return self._component_result(min(100, total_weight), status, findings)

    def _review_paragraph_texture(self, content: str) -> dict:
        findings = []
        score = 60
        paragraphs = [para.strip() for para in content.split("\n") if para.strip()]
        para_lengths = [len(para) for para in paragraphs if len(para) > 10]

        if len(para_lengths) >= 5:
            avg_len = sum(para_lengths) / len(para_lengths)
            near_avg = sum(1 for length in para_lengths if abs(length - avg_len) < avg_len * 0.3)
            uniformity = near_avg / len(para_lengths)
            if uniformity > 0.7:
                findings.append(
                    self._make_finding(
                        "WARN",
                        f"段落过于均匀: {uniformity:.0%}段落长度接近",
                        suggestion="变换段落长短，让长短句和停顿层次更明显",
                    )
                )

        transition_count = sum(len(pattern.findall(content)) for pattern in TRANSITION_WORDS)
        transition_per_k = transition_count * 1000 / max(len(content), 1)
        if transition_per_k > 3:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"连接词堆砌({transition_per_k:.1f}/千字): '然而/此外/总而言之'",
                    suggestion="删掉多余连接词，用动作和场景自然过渡",
                )
            )
            score -= 20

        starter_counts = {}
        sentences = re.split(r"[。！？\n]", content)[:30]
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            for pattern, label in SENTENCE_STARTERS:
                if pattern.match(sentence):
                    starter_counts[label] = starter_counts.get(label, 0) + 1
                    break

        max_starter = max(starter_counts.values()) if starter_counts else 0
        if max_starter > len(sentences) * 0.5 and len(sentences) > 10:
            dominant = max(starter_counts, key=starter_counts.get)
            findings.append(
                self._make_finding(
                    "WARN",
                    f"句式单一: {dominant}占比>{max_starter / len(sentences):.0%}",
                    suggestion="打破惯性句式，混合动作句、感官句和对白句",
                )
            )

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._component_result(score, status, findings)

    def _review_subtext(self, content: str) -> dict:
        findings = []
        score = 60
        total_chars = max(len(content), 1)

        explicit_count = 0
        for pattern in EXPLICIT_EXPLAIN:
            matches = pattern.findall(content)
            if matches:
                explicit_count += len(matches)
                evidence = matches[0][:80] if isinstance(matches[0], str) else str(matches[0])[:80]
                findings.append(
                    self._make_finding(
                        "WARN",
                        f"表达过于直白: '{evidence[:40]}'",
                        evidence=evidence,
                        suggestion="人物不必说出全部心里话，可用动作、停顿和反话代替",
                    )
                )

        explicit_per_k = explicit_count * 1000 / total_chars
        if explicit_per_k > 4:
            score -= 25
        elif explicit_count > self.max_explicit:
            score -= 15

        subtext_count = sum(len(pattern.findall(content)) for pattern in SUBTEXT_GOOD)
        if subtext_count < self.min_subtext:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"潜台词技法不足: {subtext_count}处(需≥{self.min_subtext})",
                    suggestion="增加冷笑、别过头、沉默和反话等间接表达",
                )
            )
            score -= 10
        elif subtext_count >= 8:
            score += 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._component_result(score, status, findings)

    def _review_setting(self, content: str) -> dict:
        findings = []
        issues_weight = 0

        physics_issues = []
        for pattern, category in PHYSICS_ANALOGY_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                for match in matches[:3]:
                    text = match[:40] if isinstance(match, str) else str(match)[:40]
                    physics_issues.append(f"{category}: '{text}'")
                issues_weight += len(matches) * 20
        if physics_issues:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"不当物理类比: {len(physics_issues)}处",
                    evidence="; ".join(physics_issues[:3]),
                    suggestion="比喻应取自自然、器物或修行经验，避免现代科学类比",
                )
            )

        realm_issues = []
        for pattern in REALM_CONTRADICTION_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                for match in matches[:2]:
                    if isinstance(match, tuple):
                        realm_issues.append("".join(match))
                    else:
                        realm_issues.append(str(match)[:40])
        if realm_issues and not any(
            word in content for word in ["越级", "跨境", "跨境界", "出其不意", "偷袭", "法宝", "秘术", "自爆", "燃烧", "耗尽了"]
        ):
            findings.append(
                self._make_finding(
                    "WARN",
                    "境界矛盾: 低境界无解释击败高境界",
                    evidence="; ".join(realm_issues[:3]),
                    suggestion="跨境战斗需明确解释: 法宝、偷袭、秘术或对方虚弱",
                )
            )
            issues_weight += 25

        for pattern, label in RULE_CONTRADICTION_MARKERS:
            matches = pattern.findall(content)
            if len(matches) >= 2:
                findings.append(
                    self._make_finding(
                        "WARN",
                        f"规则摇摆 ({label}): {len(matches)}处",
                        evidence=str(matches[:3])[:100],
                        suggestion="世界规则应明确稳定，避免写成'可以但也不可以'",
                    )
                )
                issues_weight += 15

        for _, aliases in ITEM_ALIAS_PATTERNS:
            found = [alias for alias in aliases if alias in content]
            if len(found) >= 2:
                findings.append(
                    self._make_finding(
                        "WARN",
                        f"物品别名混用: {', '.join(found)}",
                        suggestion=f"统一使用一个名称，建议'{aliases[0]}'",
                    )
                )
                issues_weight += 10

        currency_matches = CURRENCY_PATTERNS.findall(content)
        currency_systems = {match[2] for match in currency_matches}
        for primary, secondary in DUAL_CURRENCY_PAIRS:
            has_primary = any(currency in primary for currency in currency_systems)
            has_secondary = any(currency in secondary for currency in currency_systems)
            if has_primary and has_secondary:
                findings.append(
                    self._make_finding(
                        "WARN",
                        "双货币系统混用",
                        evidence=f"同时出现修仙货币{[currency for currency in currency_systems if currency in primary]}和凡间货币{[currency for currency in currency_systems if currency in secondary]}",
                        suggestion="确认是否需要双货币系统，否则统一为单一货币",
                    )
                )
                issues_weight += 10
                break

        if "灵气" in content and "灵力" in content:
            thin = re.findall(r"(稀薄|稀|少|匮乏|枯竭)", content)
            rich = re.findall(r"(充沛|充裕|丰富|浓郁|浑厚)", content)
            if thin and rich:
                findings.append(
                    self._make_finding(
                        "WARN",
                        "灵气/灵力描述矛盾",
                        evidence=f"灵气: {thin[:2]}, 灵力: {rich[:2]}",
                        suggestion="灵力源于灵气，两者状态应尽量一致或给出解释",
                    )
                )

        status = "PASS" if issues_weight == 0 else "WARNING"
        return self._component_result(min(100, issues_weight), status, findings)
