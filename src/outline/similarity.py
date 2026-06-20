#!/usr/bin/env python3
"""
similarity.py — 大纲相似度检测引擎 v0.6.5

对两个大纲进行多维度相似度分析：
1. 标题相似度 (Levenshtein 距离比率)
2. 角色名重叠度 (提取人名，比较集合)
3. 世界观关键词重叠度
4. 章节结构相似度 (章节数、卷结构)
5. 题材/风格关键词重叠度

返回:
- similarity_score: 0–100 综合相似度
- classification: high_similarity / low_similarity / uncertain
- recommendation: upgrade / same_novel / new_novel / ask_user
- detail: 各维度详细得分
"""

import re
from typing import Dict, List, Tuple, Optional


def _levenshtein_ratio(s1: str, s2: str) -> float:
    """计算 Levenshtein 距离并转为 0-1 之间的比率"""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    max_len = max(len1, len2)

    # 使用双行 DP 优化空间
    prev = list(range(len2 + 1))
    curr = [0] * (len2 + 1)

    for i in range(1, len1 + 1):
        curr[0] = i
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev

    distance = prev[len2]
    return 1.0 - (distance / max_len)


def _extract_chinese_names(text: str) -> set:
    """从文本中提取中文人名（粗略模式）

    中文人名通常为 2-3 个连续汉字，
    提取在「姓名」「角色」「人物」「主角」「配角」等附近出现的 2-3 字组合，
    以及以「李」「王」「张」「刘」「陈」「杨」「赵」「黄」「周」「吴」
    「徐」「孙」「马」「胡」「朱」「郭」「何」「林」「高」「罗」开头的二字/三字名。
    """
    surnames = set("李王张刘陈杨赵黄周吴徐孙马胡朱郭何林高罗"
                   "郑梁谢宋唐许邓韩冯曹彭曾肖田董潘袁蔡蒋余"
                   "于杜叶程苏魏吕丁任卢姚沈姜崔钟谭陆汪范金"
                   "石廖贾夏韦傅方白邹孟熊秦邱江尹薛阎段雷侯"
                   "龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤")

    names = set()

    # 方法1：提取姓氏开头的 2-3 字组合
    for i, ch in enumerate(text):
        if ch in surnames and i + 1 < len(text):
            # 二字符名
            if text[i + 1] not in "，。！？、；：""''（）《》…— \n\r\t,./!?;:()[]{}":
                names.add(text[i:i + 2])
            # 三字符名
            if i + 2 < len(text):
                if (text[i + 1] not in "，。！？、；：""''（）《》…— \n\r\t,./!?;:()[]{}"
                        and text[i + 2] not in "，。！？、；：""''（）《》…— \n\r\t,./!?;:()[]{}"):
                    names.add(text[i:i + 3])

    # 方法2：在 "主角"、"主角：", "姓名：" 等字段后提取
    for pattern in [r'(?:主角|姓名|角色|人物|男主|女主|男配|女配)[：:]\s*([^\n，。]{2,4})',
                    r'(?:主角|姓名|角色|人物|男主|女主|男配|女配)[是为叫作叫做称呼]\s*([^\n，。]{2,4})']:
        for m in re.finditer(pattern, text):
            name = m.group(1).strip()
            if 2 <= len(name) <= 4:
                names.add(name)

    return {n for n in names if 2 <= len(n) <= 4}


def _extract_world_keywords(text: str) -> set:
    """提取世界观关键词

    包括：
    - 「世界」「大陆」「星球」「宇宙」「位面」「次元」附近的名词
    - 「境界」「功法」「灵气」「修炼」「魔法」「异能」「修仙」「武道」「科技」
    - 「宗派」「门派」「学院」「联盟」「帝国」「王国」「城市」等
    - 「法则」「规则」「体系」「系统」「设定」===
    """

    # 虚词/功能词过滤器：含这些字的匹配大概率是碎句残片
    _NOISE_CHARS = set(
        "不是的了被把在和及而也就都还却只才便可但与从对向往到给让叫比将以因由为之其所中后前下上内外总各全本该此那这每某何怎什哪公开开始才能中期顺应理解改写伏笔"
    )
    # 以这些字开头的词组大概率是谓语/状语碎片，不是名词性关键词
    _BAD_STARTS = ["不是", "而是", "公开", "开始", "中期", "才能", "顺应", "理解", "改写", "者之"]

    keywords = set()

    # 正则：用非贪婪 {1,3} 限制前缀长度，减少吞入噪音
    world_patterns = [
        r'([\u4e00-\u9fff]{1,3}(?:世界|大陆|星球|宇宙|位面|次元|时空|领域|秘境))',
        r'([\u4e00-\u9fff]{1,4}(?:境界|功法|修炼|体系|法则))',
        r'([\u4e00-\u9fff]{1,4}(?:宗派|门派|学院|联盟|帝国|王国|城市|国度|圣地))',
    ]

    for pat in world_patterns:
        for m in re.finditer(pat, text):
            kw = m.group(1).strip()
            if not (2 <= len(kw) <= 6):
                continue
            if any(kw.startswith(bs) for bs in _BAD_STARTS):
                continue
            if any(c in _NOISE_CHARS for c in kw):
                continue
            keywords.add(kw)

    # 直接匹配世界观常见关键词
    world_kw_list = [
        "修仙", "魔法", "武道", "科技", "异能", "灵气", "斗气", "魔力",
        "玄幻", "奇幻", "科幻", "末世", "穿越", "重生", "系统", "金手指",
        "修真", "炼丹", "炼器", "阵法", "符箓", "御剑",
        "学院流", "凡人流", "无限流", "洪荒流",
        "宗门", "散修", "内门", "外门", "长老", "掌门",
        "法力", "神念", "神识", "元婴", "金丹", "筑基", "炼气",
        "剑修", "体修", "阵修", "丹修",
    ]
    for kw in world_kw_list:
        if kw in text:
            keywords.add(kw)

    return keywords


def _extract_chapter_structure(text: str) -> Dict:
    """提取章节结构信息

    返回: {"chapter_count": int, "volume_count": int, "avg_chapter_desc_len": float}
    """
    chapter_count = 0
    volume_count = 1

    for line in text.split("\n"):
        line = line.strip()
        if "第" in line and "章" in line:
            chapter_count += 1
        if "第" in line and "卷" in line:
            # 每出现一次"第X卷"就记一卷
            m = re.search(r'第\s*(\d+)\s*卷', line)
            if m:
                vn = int(m.group(1))
                volume_count = max(volume_count, vn)

    return {
        "chapter_count": chapter_count,
        "volume_count": volume_count,
    }


def _extract_genre_style_keywords(text: str) -> Dict:
    """提取题材/风格关键词"""
    genre_kw = {
        "修仙": "xianxia", "玄幻": "xuanhuan", "奇幻": "qihuan",
        "都市": "urban", "科幻": "scifi", "悬疑": "suspense",
        "恐怖": "horror", "历史": "history", "言情": "romance",
        "武侠": "wuxia", "军事": "military", "游戏": "game",
        "竞技": "sports", "末世": "apocalypse", "无限": "infinite",
    }
    style_kw = {
        "爽文": "shuangwen", "虐文": "nuewen", "轻松": "light",
        "严肃": "serious", "黑色": "black", "爆笑": "comedy",
        "系统": "system", "重生": "rebirth", "穿越": "transmigration",
        "单女主": "single_fl", "多女主": "harem", "无女主": "no_fl",
        "热血": "hotblood", "冷酷": "cold", "杀伐": "ruthless",
    }

    found_genre = set()
    found_style = set()

    for kw, _ in genre_kw.items():
        if kw in text:
            found_genre.add(kw)

    for kw, _ in style_kw.items():
        if kw in text:
            found_style.add(kw)

    return {"genre_keywords": found_genre, "style_keywords": found_style}


class OutlineSimilarity:
    """大纲相似度检测引擎"""

    # 各维度权重
    WEIGHTS = {
        "title": 0.15,          # 标题相似度
        "characters": 0.25,     # 角色名重叠
        "worldbuilding": 0.25,  # 世界观关键词重叠
        "chapter_structure": 0.15,  # 章节结构
        "genre_style": 0.20,    # 题材/风格
    }

    # 分类阈值
    HIGH_THRESHOLD = 70       # >=70 高相似
    LOW_THRESHOLD = 35        # <35 低相似

    def compare(self, title1: str, title2: str,
                content1: str, content2: str,
                genre1: str = "", genre2: str = "",
                style1: str = "", style2: str = "") -> Dict:
        """
        全面对比两个大纲。

        返回:
        {
            "similarity_score": int (0-100),
            "classification": "high_similarity" | "low_similarity" | "uncertain",
            "recommendation": "upgrade" | "same_novel" | "new_novel" | "ask_user",
            "detail": {
                "title_similarity": ...,
                "character_overlap": ...,
                "worldbuilding_overlap": ...,
                "chapter_structure_similarity": ...,
                "genre_style_overlap": ...,
            },
        }
        """
        # 1. 标题相似度
        title_sim = _levenshtein_ratio(title1.strip(), title2.strip())
        title_score = title_sim * 100

        # 2. 角色名重叠度
        chars1 = _extract_chinese_names(content1)
        chars2 = _extract_chinese_names(content2)
        if not chars1 and not chars2:
            char_overlap = None  # 双方均无角色名 → 不参与评分 (v0.6.5-clean3)
        else:
            union = chars1 | chars2
            intersection = chars1 & chars2
            char_overlap = len(intersection) / len(union) if union else 0.0
        char_score = char_overlap * 100 if char_overlap is not None else None

        # 3. 世界观关键词重叠
        world1 = _extract_world_keywords(content1)
        world2 = _extract_world_keywords(content2)
        if not world1 and not world2:
            world_overlap = None  # 双方均无世界观关键词 → 不参与评分 (v0.6.5-clean3)
        else:
            union_w = world1 | world2
            intersection_w = world1 & world2
            world_overlap = len(intersection_w) / len(union_w) if union_w else 0.0
        world_score = world_overlap * 100 if world_overlap is not None else None

        # 4. 章节结构相似度
        struct1 = _extract_chapter_structure(content1)
        struct2 = _extract_chapter_structure(content2)
        ch_diff = abs(struct1["chapter_count"] - struct2["chapter_count"])
        max_ch = max(struct1["chapter_count"], struct2["chapter_count"], 1)
        ch_sim = 1.0 - min(ch_diff / max_ch, 1.0)

        vol_diff = abs(struct1["volume_count"] - struct2["volume_count"])
        max_vol = max(struct1["volume_count"], struct2["volume_count"], 1)
        vol_sim = 1.0 - min(vol_diff / max_vol, 1.0)

        # v0.6.5-clean5: 双方均为 0 章 → 不参与评分
        if struct1["chapter_count"] == 0 and struct2["chapter_count"] == 0:
            struct_score = None
        else:
            struct_score = (ch_sim * 0.6 + vol_sim * 0.4) * 100

        # 5. 题材/风格关键词重叠
        gs1 = _extract_genre_style_keywords(content1)
        gs2 = _extract_genre_style_keywords(content2)

        genre_kw1 = gs1["genre_keywords"]
        genre_kw2 = gs2["genre_keywords"]
        style_kw1 = gs1["style_keywords"]
        style_kw2 = gs2["style_keywords"]

        if not genre_kw1 and not genre_kw2:
            genre_overlap = 0.5  # 无法判断
        else:
            union_g = genre_kw1 | genre_kw2
            intersection_g = genre_kw1 & genre_kw2
            genre_overlap = len(intersection_g) / len(union_g) if union_g else 0.5

        if not style_kw1 and not style_kw2:
            style_overlap = 0.5
        else:
            union_s = style_kw1 | style_kw2
            intersection_s = style_kw1 & style_kw2
            style_overlap = len(intersection_s) / len(union_s) if union_s else 0.5

        genre_style_score = (genre_overlap * 0.5 + style_overlap * 0.5) * 100

        # 综合得分 — 跳过 None 维度（双方均无数据），重新归一化权重
        scores_and_weights = [
            (title_score, self.WEIGHTS["title"]),
            (char_score, self.WEIGHTS["characters"]),
            (world_score, self.WEIGHTS["worldbuilding"]),
            (struct_score, self.WEIGHTS["chapter_structure"]),
            (genre_style_score, self.WEIGHTS["genre_style"]),
        ]
        active_scores = [(s, w) for s, w in scores_and_weights if s is not None]
        if active_scores:
            total_weight = sum(w for _, w in active_scores)
            raw_score = sum(s * (w / total_weight) for s, w in active_scores)
        else:
            raw_score = 50.0  # 所有维度均无数据 → 中性分
        similarity_score = min(round(raw_score), 100)

        # 分类
        if similarity_score >= self.HIGH_THRESHOLD:
            classification = "high_similarity"
            recommendation = "upgrade"
        elif similarity_score < self.LOW_THRESHOLD:
            classification = "low_similarity"
            recommendation = "new_novel"
        else:
            classification = "uncertain"
            # 进一步判断 (v0.6.5-clean3: 处理 None 维度)
            ch_ov = char_overlap if char_overlap is not None else 0.0
            wo_ov = world_overlap if world_overlap is not None else 0.0
            if ch_ov >= 0.6 and wo_ov >= 0.5:
                recommendation = "same_novel"
            elif ch_ov < 0.2 and wo_ov < 0.2:
                recommendation = "new_novel"
            else:
                recommendation = "ask_user"

        return {
            "similarity_score": similarity_score,
            "classification": classification,
            "recommendation": recommendation,
            "detail": {
                "title_similarity": {
                    "score": round(title_score, 1),
                    "weight": self.WEIGHTS["title"],
                    "title1": title1,
                    "title2": title2,
                },
                "character_overlap": {
                    "score": round(char_score, 1) if char_score is not None else None,
                    "weight": self.WEIGHTS["characters"],
                    "chars1": sorted(list(chars1)),
                    "chars2": sorted(list(chars2)),
                    "intersection": sorted(list(chars1 & chars2)),
                    "overlap_ratio": round(char_overlap, 3) if char_overlap is not None else None,
                },
                "worldbuilding_overlap": {
                    "score": round(world_score, 1) if world_score is not None else None,
                    "weight": self.WEIGHTS["worldbuilding"],
                    "keywords1": sorted(list(world1)),
                    "keywords2": sorted(list(world2)),
                    "intersection": sorted(list(world1 & world2)),
                    "overlap_ratio": round(world_overlap, 3) if world_overlap is not None else None,
                },
                "chapter_structure_similarity": {
                    "score": round(struct_score, 1) if struct_score is not None else None,
                    "weight": self.WEIGHTS["chapter_structure"],
                    "outline1": {"chapters": struct1["chapter_count"], "volumes": struct1["volume_count"]},
                    "outline2": {"chapters": struct2["chapter_count"], "volumes": struct2["volume_count"]},
                },
                "genre_style_overlap": {
                    "score": round(genre_style_score, 1),
                    "weight": self.WEIGHTS["genre_style"],
                    "genre_overlap": sorted(list(genre_kw1 & genre_kw2)),
                    "style_overlap": sorted(list(style_kw1 & style_kw2)),
                    "overlap_ratio": round((genre_overlap + style_overlap) / 2, 3),
                },
            },
        }
