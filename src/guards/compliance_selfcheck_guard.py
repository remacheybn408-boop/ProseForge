#!/usr/bin/env python3
"""
compliance_selfcheck_guard.py — 投稿合规自查门禁 v0.4.0

唯一可以输出 BLOCK 状态的门禁。
检查中文文本中的平台合规风险。

风险类别:
- underage_risk: 未成年人不当内容
- explicit_sexual: 露骨性内容
- extreme_gore: 极端血腥/酷刑
- crime_tutorial: 违法教程
- hate_speech: 歧视/仇恨
- political_sensitivity: 政治敏感（保守匹配，避免误报）
- ad_spam: 引流/广告
- plagiarism_risk: 高度独特的短语（仅提示）

风险等级: none / low / medium / high
high → BLOCK, medium → WARNING, low → PASS

用法:
  python scripts/compliance_selfcheck_guard.py \
    --input chapter.txt --chapter-no 1 --out report.json
"""
import re, json, sys, argparse
from pathlib import Path
from typing import Dict, List, Tuple


# ═══════════════════════════════════════════════════
# 关键词模式库
# ═══════════════════════════════════════════════════

RISK_PATTERNS = {
    "underage_risk": {
        "high": [
            re.compile(r'(未?成年|少年|少女|儿童|孩子|小孩).{0,20}(性|爱|欲|诱|侵犯|猥亵|裸|淫)'),
            re.compile(r'(性|诱).{0,20}(未?成年|少年|少女|儿童|孩子|小孩)'),
            re.compile(r'童.{0,5}(妓|娼|性|裸|色)'),
            re.compile(r'幼.{0,5}(交|女|童|齿)'),
        ],
        "medium": [
            re.compile(r'未?成年人.{0,30}(情色|色情|艳|欲)'),
            re.compile(r'(小学|中学|高中).{0,30}(性行为|情爱|淫)'),
        ],
        "low": [
            re.compile(r'未成年.{0,50}(恋爱|牵手|亲吻|拥抱)'),
        ],
    },
    "explicit_sexual": {
        "high": [
            re.compile(r'(性交|交合|交媾|云雨|房事|行房|床笫)'),
            re.compile(r'(插入|抽插|进出).{0,10}(体内|阴道|肛门|私处|下体)'),
            re.compile(r'(高潮|射精|勃起|阳具|阴茎|阴道|阴蒂|龟头|睾丸)'),
            re.compile(r'(精液|淫水|爱液|体液).{0,10}(流出|喷|射|涌)'),
            re.compile(r'(口交|肛交|手淫|自慰|慰安)'),
        ],
        "medium": [
            re.compile(r'(裸|赤).{0,10}(体|身|露)'),
            re.compile(r'(情欲|肉欲|淫|荡|骚).{0,10}(难耐|澎湃|汹涌)'),
            re.compile(r'(抚摸|爱抚|挑逗).{0,20}(敏感|私密|禁忌)'),
            re.compile(r'(春药|媚药|催情|迷情)'),
        ],
        "low": [
            re.compile(r'(暧昧|旖旎|缠绵).{0,30}(床|夜|寝)'),
            re.compile(r'(亲吻|深吻|长吻).{0,20}(贪婪|热烈|缠绵)'),
        ],
    },
    "extreme_gore": {
        "high": [
            re.compile(r'(肢解|分尸|碎尸|剁碎|绞肉|碾碎)'),
            re.compile(r'(剥皮|抽筋|挖眼|割舌|断肢|斩首|掏心)'),
            re.compile(r'(内脏|肠子|器官).{0,10}(流|掉|露|挂|散)'),
            re.compile(r'(血.{0,3}浆|血.{0,3}泊|血.{0,3}腥|人.{0,3}肉)'),
            re.compile(r'(酷刑|凌迟|炮烙|车裂|腰斩)'),
        ],
        "medium": [
            re.compile(r'(断.{0,3}(手|脚|腿|臂|指))'),
            re.compile(r'(伤口|伤痕).{0,10}(深可见骨|血肉模糊|触目惊心)'),
            re.compile(r'(鲜血|血流).{0,10}(喷涌|狂喷|如注|不止)'),
        ],
        "low": [
            re.compile(r'(受伤|流血|伤口).{0,30}(疼痛|痛苦|难忍)'),
        ],
    },
    "crime_tutorial": {
        "high": [
            re.compile(r'(下毒|投毒|制毒|吸毒|贩毒).{0,10}(方法|步骤|教程|指南|技巧)'),
            re.compile(r'(杀人|谋杀|暗杀).{0,10}(方法|技巧|步骤|不留痕迹|完美)'),
            re.compile(r'(制造|制作).{0,5}(炸弹|炸药|燃烧弹|毒药|迷药)'),
            re.compile(r'(诈骗|洗钱|套现|刷单).{0,10}(教程|方法|详解|指南)'),
            re.compile(r'(黑客|入侵|破解|盗号).{0,10}(教程|工具|方法|技巧)'),
            re.compile(r'(盗窃|抢劫|偷|抢).{0,10}(技巧|方法|窍门|指南)'),
        ],
        "medium": [
            re.compile(r'(伪造|假冒|仿制).{0,10}(证件|公章|文件)'),
            re.compile(r'(非法.{0,5}(集资|传销|拘禁|买卖))'),
        ],
        "low": [],
    },
    "hate_speech": {
        "high": [
            re.compile(r'(杀光|灭掉|铲除|清除|消灭).{0,5}(所有|一切|全部).{0,10}(人|族|国|民)'),
            re.compile(r'(种族|民族).{0,10}(低劣|下等|劣等|该杀|该死)'),
            re.compile(r'(歧视|仇恨|敌视).{0,10}(种族|民族|宗教|地域|性别)'),
        ],
        "medium": [
            re.compile(r'(日寇|鬼子|洋鬼子|白皮猪|黑鬼|阿三|棒子).{0,10}(该|都|全)'),
            re.compile(r'(女性|女人).{0,10}(天生.{0,5}(弱|蠢|贱|贱货|花瓶))'),
        ],
        "low": [],
    },
    "political_sensitivity": {
        "high": [
            # 极其保守的匹配 — 仅匹配明确的违规内容
            re.compile(r'(台独|藏独|疆独|港独)'),
            re.compile(r'(法轮功|法轮大法)'),
        ],
        "medium": [
            re.compile(r'(分裂.{0,5}(国家|祖国|中国|中华))'),
        ],
        "low": [
            # 不添加 low 级别匹配以避免误报
        ],
    },
    "ad_spam": {
        "high": [
            re.compile(r'(加微信|加QQ|加群).{0,20}(小说|更新|全文|资源)'),
            re.compile(r'(关注公众号|扫码关注|搜索公众号).{0,30}(小说|阅读|看书)'),
            re.compile(r'(充值|付费|订阅|购买).{0,10}(看完全文|解锁章节)'),
        ],
        "medium": [
            re.compile(r'(求.{0,5}(打赏|月票|推荐票|收藏|订阅|关注))'),
            re.compile(r'(读者群|书友群|粉丝群).{0,10}(加|进|来)'),
        ],
        "low": [
            re.compile(r'(喜欢|好看).{0,10}(收藏|关注|点赞)'),
        ],
    },
    "plagiarism_risk": {
        # 不设置 high/medium — plagiarism_risk 仅作提示
        "high": [],
        "medium": [],
        "low": [
            # 检测高度独特的短语模式（仅提示，不做判断）
            re.compile(r'三十年河东三十年河西莫欺少年穷'),
            re.compile(r'我要这天再遮不住我眼'),
            re.compile(r'天地不仁以万物为刍狗'),
        ],
    },
}


# ═══════════════════════════════════════════════════
# 检测逻辑
# ═══════════════════════════════════════════════════

def check_category(text: str, category: str, patterns: dict) -> dict:
    """
    检查单个风险类别。
    返回: {"risk": "none"|"low"|"medium"|"high", "matches": [...], "count": N}
    """
    all_matches = []

    for level in ("high", "medium", "low"):
        for pattern in patterns.get(level, []):
            for m in pattern.finditer(text):
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 30)
                all_matches.append({
                    "level": level,
                    "text": m.group()[:80],
                    "context": text[start:end][:100],
                    "position": m.start(),
                })

    if not all_matches:
        return {"risk": "none", "matches": [], "count": 0}

    # 取最高风险级别
    levels = [m["level"] for m in all_matches]
    if "high" in levels:
        risk = "high"
    elif "medium" in levels:
        risk = "medium"
    else:
        risk = "low"

    return {
        "risk": risk,
        "matches": all_matches[:10],
        "count": len(all_matches),
    }


def build_report(text: str, chapter_no: int = 1) -> dict:
    """构建合规自查报告"""
    risks = {}
    blocked_categories = []
    warning_categories = []
    pass_categories = []

    for category, patterns in RISK_PATTERNS.items():
        result = check_category(text, category, patterns)
        risks[category] = result

        if result["risk"] == "high":
            blocked_categories.append(category)
        elif result["risk"] == "medium":
            warning_categories.append(category)
        else:  # low or none
            pass_categories.append(category)

    # 裁决
    if blocked_categories:
        status = "BLOCK"
    elif warning_categories:
        status = "WARNING"
    else:
        status = "PASS"

    # 构建建议
    suggestions = []
    if blocked_categories:
        suggestions.append(
            f"检测到高风险内容: {', '.join(blocked_categories)}。"
            f"请修改相关内容后重新提交。"
        )
    if warning_categories:
        suggestions.append(
            f"以下类别存在中风险内容，建议审查: {', '.join(warning_categories)}。"
        )

    # 提取匹配样本
    risk_details = {}
    for cat, result in risks.items():
        if result["risk"] != "none":
            risk_details[cat] = {
                "risk_level": result["risk"],
                "match_count": result["count"],
                "samples": [m["text"][:60] for m in result["matches"][:5]],
            }

    return {
        "guard": "compliance_selfcheck_guard",
        "version": "v0.4.0",
        "status": status,
        "chapter_no": chapter_no,
        "risks": {
            cat: {
                "risk_level": result["risk"],
                "match_count": result["count"],
            }
            for cat, result in risks.items()
        },
        "risk_details": risk_details,
        "blocked_categories": blocked_categories,
        "warnings_categories": warning_categories,
        "passed_categories": pass_categories,
        "suggestions": suggestions,
        "hard_fail": status == "BLOCK",
    }


# ═══════════════════════════════════════════════════
# Guard Registry entry point (v0.4.5)
# ═══════════════════════════════════════════════════

def run_compliance_selfcheck(content: str, chapter_no: int = 0,
                             *args, **kwargs) -> dict:
    """Guard Registry entry point. Wraps build_report()."""
    return build_report(content, chapter_no)


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Compliance Self-Check Guard")
    parser.add_argument("--input", required=True, help="章节 TXT 文件路径")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--out", default=None, help="输出 JSON 报告路径")
    args = parser.parse_args()

    content = Path(args.input).read_text(encoding="utf-8")
    report = build_report(content, args.chapter_no)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    if report["status"] == "BLOCK":
        print(f"\n[BLOCK] Compliance: {len(report['blocked_categories'])} high-risk categories")
    elif report["status"] == "WARNING":
        print(f"\n[WARN] Compliance: {len(report['warnings_categories'])} medium-risk categories")
    else:
        print(f"\n[OK] Compliance check passed")


if __name__ == "__main__":
    main()
