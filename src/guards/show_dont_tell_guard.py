#!/usr/bin/env python3
"""
show_dont_tell_guard.py — AI 总结句检测门禁 v0.3.1-qgp

检查旁白中是否出现 AI 总结腔、空泛危机句、命运齿轮句等。
重点抓：
1. 他终于明白 / 她意识到
2. 真正的危机才开始
3. 命运开始 / 命运的齿轮
4. 关系发生变化
5. 前所未有的恐惧
6. 巨大的阴谋
7. 无法回头
8. 望远镜句（多年以后...）

策略: Phase 2 — 先 WARNING，Phase 3 — 2个以上升级 FAIL
"""
import re, json, sys, argparse
from pathlib import Path

# ═══════════════════════════════════════════════════
# 禁用模式
# ═══════════════════════════════════════════════════

FORBIDDEN_PATTERNS = [
    # ── 总结性顿悟 ──
    (re.compile(r'(他|她|他们|她们)(终于|突然|忽然|一下子|猛地)(明白|意识到|懂了|理解了|知道了|看透了|醒悟了|想通了)'), "总结顿悟"),
    (re.compile(r'(终于|突然|忽然|猛地)(明白|意识到|懂了|理解了|知道了|看透|醒悟|想通)了'), "总结顿悟"),
    (re.compile(r'那一刻.{1,15}(终于|突然|忽然).{1,10}(明白|意识到|懂了|知道了)'), "那一刻顿悟"),

    # ── 空泛危机 ──
    (re.compile(r'真正的危机才(刚刚|刚刚|刚要|正要)(开始|降临)'), "空泛危机"),
    (re.compile(r'真正的(风暴|考验|危险|灾难|威胁).{0,10}(即将|正要|就要|马上)'), "空泛危机"),
    (re.compile(r'更大的(阴谋|危险|威胁|风暴|挑战).{0,10}(正在|即将|已经)'), "空泛危机"),
    (re.compile(r'没人知道(等待|等着).{1,10}的(是什么|会是)'), "空泛悬念"),

    # ── 命运齿轮 ──
    (re.compile(r'命运的齿轮(开始|已经|再次)转动'), "命运齿轮"),
    (re.compile(r'命运的(轨迹|捉弄|安排)'), "命运句"),
    (re.compile(r'一切都是(命中注定|天意|命运)'), "命运句"),
    (re.compile(r'这就是(他|她|他们|她们)(的|这辈子的)命'), "命运句"),

    # ── 空泛关系 ──
    (re.compile(r'关系发生.{0,5}(微妙|变化|改变)'), "空泛关系"),
    (re.compile(r'关系变得(不同|不一样)'), "空泛关系"),
    (re.compile(r'从此再也不一样了'), "空泛关系"),
    (re.compile(r'某种说不清的东西在.{1,10}之间'), "空泛关系"),

    # ── 空泛情绪 ──
    (re.compile(r'前所未有(的|那种)(恐惧|害怕|恐俱|惊慌|震惊|震撼)'), "空泛情绪"),
    (re.compile(r'无法(描述|形容|言说)(的|那种)(恐惧|感觉|情绪)'), "空泛情绪"),
    (re.compile(r'说不出的(恐惧|感觉|情绪)'), "空泛情绪"),
    (re.compile(r'(五味杂陈|百感交集|难以名状.{0,5}感觉)'), "空泛情绪"),

    # ── 望远镜句 ──
    (re.compile(r'多年以后.{0,20}回想起'), "望远镜句"),
    (re.compile(r'他那时还不知道.{0,20}'), "望远镜句"),
    (re.compile(r'她那时还不知道.{0,20}'), "望远镜句"),
    (re.compile(r'那时的(他们|她们)还不知道'), "望远镜句"),
    (re.compile(r'很久以后.{0,10}才会明白'), "望远镜句"),
    (re.compile(r'这将是.{0,10}最后一次'), "望远镜句"),

    # ── 说教腔 ──
    (re.compile(r'要知道.{0,10}从来都不是'), "说教腔"),
    (re.compile(r'说到底.{0,10}不过是'), "说教腔"),
    (re.compile(r'人生就是这样'), "说教腔"),
    (re.compile(r'这就是修仙界(的残酷|的法则|的规则)'), "说教腔"),
    (re.compile(r'在这个弱肉强食的世界'), "说教腔"),
    (re.compile(r'真正的强者.{0,15}'), "说教腔"),

    # ── 无法回头 ──
    (re.compile(r'无法回头.{0,5}(的|了|之路|路)'), "无法回头"),
    (re.compile(r'没有回头路'), "无法回头"),
]


def extract_narration(content):
    """提取旁白（去掉对白引号内容）"""
    return re.sub(r'[""「」][^""「」]+[""「」]', '', content)


def run_show_dont_tell_check(content, chapter_no):
    """主入口"""
    narration = extract_narration(content)

    matches = []
    for pattern, label in FORBIDDEN_PATTERNS:
        for m in pattern.finditer(narration):
            start = max(0, m.start() - 20)
            end = min(len(narration), m.end() + 20)
            matches.append({
                "pattern": label,
                "text": m.group()[:60],
                "context": narration[start:end][:80],
                "position": m.start()
            })

    match_count = len(matches)

    # ── 分类统计 ──
    by_type = {}
    for m in matches:
        t = m["pattern"]
        by_type[t] = by_type.get(t, 0) + 1

    summary_sentences = sum(1 for m in matches if "顿悟" in m["pattern"])
    emotion_tellings = sum(1 for m in matches if m["pattern"] in ("空泛情绪", "说教腔"))
    fate_crisis = sum(1 for m in matches if m["pattern"] in ("命运齿轮", "命运句", "空泛危机"))

    # ── 裁决 ──
    # Phase 2: 0-2 matches → PASS, 3-4 → WARNING, 5+ → FAIL
    if match_count <= 2:
        status = "PASS"
        decision = "PASS"
    elif match_count <= 4:
        status = "WARNING"
        decision = "WARNING"
    else:
        status = "FAIL"
        decision = "FAIL"

    report = {
        "status": status,
        "final_decision": decision,
        "chapter_no": chapter_no,
        "total_matches": match_count,
        "matches": matches[:10],
        "by_type": by_type,
        "summary_sentence_count": summary_sentences,
        "emotion_telling_count": emotion_tellings,
        "fate_crisis_count": fate_crisis,
        "action_replacement_needed": [m["text"] for m in matches[:5]],
        "show_dont_tell_pass": status == "PASS",
        "warnings": [f"{m['pattern']}: '{m['text'][:40]}'" for m in matches[:5]] if match_count > 0 else [],
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Show Don't Tell Guard")
    parser.add_argument("content_file", help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    content = Path(args.content_file).read_text(encoding="utf-8")
    report = run_show_dont_tell_check(content, args.chapter_no)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if report["status"] == "FAIL":
        print(f"\n[FAIL] Show-don't-tell check: {report['total_matches']} AI summary patterns found")
        sys.exit(0)  # Phase 2 still exits 0
    elif report["status"] == "WARNING":
        print(f"\n[WARN] Show-don't-tell: {report['total_matches']} patterns (threshold: 2)")
    else:
        print(f"\n[OK] Show-don't-tell check passed")


if __name__ == "__main__":
    main()
