#!/usr/bin/env python3
"""
concrete_anchor_guard.py — 具体锚点门禁 v0.4.0

确保章节有物理物件、身体动作、场景锚点、可见后果，
而非只有情绪和概念叙述。

通过 500 字符窗口扫描，每个窗口至少需要：
1 个物件锚点 + 1 个体动作 + 1 个场景锚点。
三个全缺的窗口被标记。

用法:
  python scripts/concrete_anchor_guard.py \
    --input chapter.txt --chapter-no 1 [--output report.json]
"""
import re, json, sys, argparse
from pathlib import Path
from typing import List, Dict
from consequence_lexicon import (
    find_all_consequences,
    count_visible_consequences,
    has_minimum_visible_cost,
)


# ═══════════════════════════════════════════════════
# 检测词库
# ═══════════════════════════════════════════════════

# 物理物件：碗、门、血、石、铜钱、袖口等
OBJECT_PATTERNS = re.compile(
    r'(碗|杯|壶|炉|灯|烛|火|水|土|石|木|金|玉|铜|铁|银|纸|竹|布|皮|绳|链|锁|钥'
    r'|门|窗|墙|地|天|桌|椅|床|凳|柜|箱|匣|盒|瓶|罐|盆|桶|缸|锅|铲|勺|筷'
    r'|剑|刀|枪|棍|鞭|弓|箭|盾|甲|袍|衣|袖|鞋|靴|帽|巾|带|环|镯|簪|钗|佩'
    r'|印|符|丹|药|针|线|镜|梳|扇|伞|灯|墨|砚|笔|简|册|卷|轴|琴|棋|棋盘'
    r'|血|汗|泪|灰|尘|泥|沙|雾|烟|光|影|痕|纹|线|点|斑|迹|印|渍|裂|缝|孔'
    r'|矿|洞|坑|井|路|道|桥|河|湖|海|山|峰|谷|林|树|草|花|叶|根|枝|藤'
    r'|铜钱|玉牌|令牌|竹简|袖口|石阶|窗纸|井沿|门槛|屋檐|案几|烛台|香炉'
    r'|铁链|铜环|银针|金印|木匣|皮囊|布袋|麻绳|石板|瓦片|砖块|碎瓦|残垣'
    r'|符纸|丹炉|药瓶|剑鞘|刀柄|弓弦|箭囊|盾面|甲片|血痕|泪痕|灰尘|泥土'
    r'|手掌|手指|足印|足迹|毛发|骨头|牙齿|鳞片|羽毛|爪痕|蹄印)'
)

# 身体动作：抬手、蹲下、转身、推开
BODY_ACTION_PATTERNS = re.compile(
    r'(抬手|举手|挥手|摆手|放手|松手|握手|拍手|击掌|伸[手指出]|缩[手回]'
    r'|抬[头眼眉]|低头|点头|摇头|回头|转头|扭头|侧头|仰头|垂首'
    r'|站[起立直定稳]|起[身来立站]|蹲下|坐下|起身|躺下|卧倒|趴下|跪[下倒]'
    r'|走[过去进开出回]|跑[过去进开出回]|跳[起下过跃入出]|跨[过进出]|退[后下回开步]'
    r'|转[身过头来去]|侧身|翻身|翻身|翻身|翻身|弯[腰下身]|直[起身腰]|挺[身胸直]'
    r'|推[开门进出倒]|拉[开门住进出]|踢[开飞翻倒]|踹[开门飞]|踩[上下住碎]|踏[入上进步]'
    r'|抓[住起取紧]|握[住紧拳]|捏[住碎紧]|掐[住灭断]|拧[开紧断转]|扭[头转身断]'
    r'|拍[打击桌面肩]|敲[门击桌面]|捶[打桌面胸]|砸[下去碎开]|摔[倒下碎去]|扔[出去下]|抛[出起下]'
    r'|拔[剑刀出起]|抽[剑刀出身出手]|挥[剑刀手动]|砍[下去断劈]|刺[入进去穿]|劈[开下去]|斩[断落下去]'
    r'|撩[起开]|掀[开起翻]|揭[开起下]|扯[住开下掉]|撕[开碎裂破]|咬[住碎裂牙]|嚼[碎吞咽]|咽[下喉去]'
    r'|吸[气进去入]|呼[气出吸]|吐[出气纳血]|咳[嗽出血]|喷[出射血火]|吹[灭熄气灰]'
    r'|摸[索到着过]|触[摸碰到及]|碰[到撞翻倒]|撞[上开倒飞]|磕[头碰到]|倒[下退去飞]|跌[倒坐下落]'
    r'|扶[住起来墙]|撑[住起地墙]|托[住起举]|举[起手杯]|端[起碗杯]|捧[起住着]'
    r'|穿[上衣服好]|脱[下掉去衣]|披[上肩衣]|裹[住紧身]|缠[上绕住]|系[上紧好]|解[开下除]'
    r'|睁[开眼]|闭[上眼目]|眨[眼目]|瞪[大眼目]|眯[起眼]|盯[着住看]|扫[视过一眼]|瞥[见了一眼]'
    r'|听[见到说]|闻[到见了]|嗅[到了]|舔[了着]|尝[了到]|抿[了嘴唇一口]'
    r'|抿[嘴唇]|咬[牙唇]|跺[脚地]|顿[足脚]|搓[手揉]|磨[牙蹭]'
    r'|手指|指尖|手掌|掌心|拳头|手背|手腕|手臂|胳膊|手肘|肩膀|肩头|后背|脊背|腰|腰身'
    r'|大腿|小腿|膝盖|脚踝|脚掌|脚趾|脚跟|脚尖|脚底|脚跟|步伐|步子|脚步)'
)

# 场景锚点：光、温度、声音、气味、干湿
SCENE_ANCHOR_PATTERNS = re.compile(
    r'(光|亮|暗|黑|阴|影|明|昏|薄光|微光|月光|日光|烛光|灯火|阳光'
    r'|冷|热|暖|凉|寒|烫|冰|温|燥|闷|潮|湿|干|润|燥热|湿冷|阴冷|闷热'
    r'|声|音|响|静|寂|默|无声|声音|声响|回音|脚步[声]|蹄[声]|水[声滴]|风[声]'
    r'|雷[声]|钟[声]|鼓[声]|琴[声]|笛[声]|铃[声]|门[声响]|窗[声响]'
    r'|气[味息]|[香臭腥臊膻焦糊霉腐酸]味|[香臭腥臊焦糊霉腐酸]气'
    r'|风|雾|雨|雪|霜|露|霾|霞|虹|雷|电|云|天[空色]'
    r'|湿[了润漉漉淋淋透]|干[了燥巴巴渴枯涸裂]'
    r'|温度|湿度|光线|亮度|暗度|色[调泽彩光]'
    r'|霉[味斑]|水[渍滴迹]|汗[渍水迹]|血[迹渍]|锈[迹斑]|灰[尘土烬]'
    r'|漏[水风光雨]|透[光风过]|渗[水出血]|滴[水血落]|流[淌下出血汗泪]'
    r'|风[吹过刮起]|沙沙|呼呼|哗哗|滴答|哗啦|轰隆|嘎吱|咔嗒)'
)

# 可见后果：裂开、湿了、破皮、缺了一块、渗血
VISIBLE_CONSEQUENCE_PATTERNS = re.compile(
    r'(裂开|裂缝|碎裂|破碎|断裂|折断|崩塌|倒塌|散落|崩溃'
    r'|缺口|缺角|缺一块|少一截|残缺|破损|损伤|损坏'
    r'|湿透|干枯|烧焦|烫伤|冻伤|冻裂'
    r'|肿起|青紫|红肿|淤血|渗血|渗水|流血|滴血|出血|见血|露骨|破皮|破口|破相'
    r'|擦伤|割伤|刺伤|刺穿|划伤|砸伤|砸碎|撞伤|撞碎|摔伤|摔碎'
    r'|歪斜|弯曲|凹陷|凸起|变形'
    r'|落下|掉落|脱落|消失|模糊|变淡'
    r'|染红|染湿|浸湿|浸透|沾上|沾湿)'
)


# ═══════════════════════════════════════════════════
# 检测函数
# ═══════════════════════════════════════════════════

def detect_object_anchors(text: str) -> int:
    """统计物理物件数量"""
    return len(OBJECT_PATTERNS.findall(text))


def detect_body_actions(text: str) -> int:
    """统计身体动作数量"""
    return len(BODY_ACTION_PATTERNS.findall(text))


def detect_scene_anchors(text: str) -> int:
    """统计场景锚点数量"""
    return len(SCENE_ANCHOR_PATTERNS.findall(text))


def detect_visible_consequences(text: str) -> int:
    """统计可见后果数量"""
    return len(VISIBLE_CONSEQUENCE_PATTERNS.findall(text))


# ═══════════════════════════════════════════════════
# 窗口分析
# ═══════════════════════════════════════════════════

def split_into_windows(text: str, window_size: int = 500) -> List[str]:
    """将文本按窗口大小切分（尽量在句号处切）"""
    if not text.strip():
        return []

    windows = []
    pos = 0
    text_len = len(text)

    while pos < text_len:
        end = min(pos + window_size, text_len)

        # 尝试在句号、问号、感叹号、换行处切
        if end < text_len:
            # 向后找最近的自然断点
            for cut_char in ['\n', '。', '！', '？', '；']:
                cut_pos = text.rfind(cut_char, pos, end)
                if cut_pos > pos + window_size // 2:
                    end = cut_pos + 1
                    break

        window_text = text[pos:end].strip()
        if window_text:
            windows.append(window_text)
        pos = end

    return windows


def analyze_windows(windows: List[str]) -> Dict:
    """分析每个窗口的锚点覆盖情况"""
    total = len(windows)
    if total == 0:
        return {
            "total_windows": 0,
            "windows_with_object": 0,
            "windows_with_body": 0,
            "windows_with_scene": 0,
            "window_pass_rate": 1.0,
            "missing_all": [],
            "missing_types": []
        }

    wins_with_object = 0
    wins_with_body = 0
    wins_with_scene = 0
    missing_all = []

    for i, w in enumerate(windows):
        has_obj = detect_object_anchors(w) > 0
        has_body = detect_body_actions(w) > 0
        has_scene = detect_scene_anchors(w) > 0

        if has_obj:
            wins_with_object += 1
        if has_body:
            wins_with_body += 1
        if has_scene:
            wins_with_scene += 1

        # 三种全缺的窗口
        if not has_obj and not has_body and not has_scene:
            missing_all.append({
                "window_index": i + 1,
                "sample": w[:80]
            })

    # 缺失类型统计
    missing_types = []
    obj_rate = wins_with_object / total
    body_rate = wins_with_body / total
    scene_rate = wins_with_scene / total

    if obj_rate < 0.6:
        missing_types.append("object_anchors")
    if body_rate < 0.6:
        missing_types.append("body_actions")
    if scene_rate < 0.6:
        missing_types.append("scene_anchors")

    # 窗口通过率：至少满足其中一种的窗口比例
    passing = sum(
        1 for w in windows
        if detect_object_anchors(w) > 0
        or detect_body_actions(w) > 0
        or detect_scene_anchors(w) > 0
    )
    pass_rate = passing / total if total > 0 else 1.0

    return {
        "total_windows": total,
        "windows_with_object": wins_with_object,
        "windows_with_body": wins_with_body,
        "windows_with_scene": wins_with_scene,
        "window_pass_rate": round(pass_rate, 3),
        "missing_all": missing_all,
        "missing_types": missing_types
    }


# ═══════════════════════════════════════════════════
# 主检查函数
# ═══════════════════════════════════════════════════

def run_concrete_anchor_check(content: str, chapter_no: int) -> dict:
    """执行具体锚点门禁检查，返回报告 dict"""

    windows = split_into_windows(content, 500)
    window_analysis = analyze_windows(windows)

    # ── 全局统计 ──
    total_objects = detect_object_anchors(content)
    total_body = detect_body_actions(content)
    total_scene = detect_scene_anchors(content)
    total_consequences = detect_visible_consequences(content)

    # ── 构建 flags 和 suggestions ──
    flags = []
    suggestions = []

    # 窗口通过率过低
    if window_analysis["window_pass_rate"] < 0.5:
        flags.append({
            "level": "WARNING",
            "type": "LOW_WINDOW_PASS_RATE",
            "message": (
                f"窗口通过率 {window_analysis['window_pass_rate']:.0%}，"
                f"超过一半窗口缺少物件/动作/场景锚点。"
            )
        })
        suggestions.append(
            "每 500 字至少加入一个可触摸的物件、一个身体动作和一个场景细节（光/声/温度/气味）。"
        )

    # 缺失类型
    if window_analysis["missing_types"]:
        type_names = {
            "object_anchors": "物理物件",
            "body_actions": "身体动作",
            "scene_anchors": "场景锚点",
        }
        missing_names = [
            type_names.get(t, t) for t in window_analysis["missing_types"]
        ]
        flags.append({
            "level": "WARNING",
            "type": "MISSING_ANCHOR_TYPES",
            "message": f"章节缺乏以下锚点类型：{', '.join(missing_names)}。"
        })
        suggestions.append(
            f"增加{'、'.join(missing_names)}相关的具体描写，让场景更有质感。"
        )

    # 三缺一窗口过多
    missing_all_count = len(window_analysis["missing_all"])
    if missing_all_count > max(1, window_analysis["total_windows"] * 0.3):
        flags.append({
            "level": "WARNING",
            "type": "EMPTY_WINDOWS",
            "message": (
                f"{missing_all_count}/{window_analysis['total_windows']} 个窗口"
                f" 完全缺少物件/动作/场景锚点。"
            )
        })
        suggestions.append(
            "检查空白窗口，确保每个场景段落都有可感知的物理世界细节。"
        )

    # 可见后果检测 — 综合传统检测 + consequence_lexicon
    lexicon_passed, lexicon_count, lexicon_details = has_minimum_visible_cost(content, min_cost=2)
    has_consequences = total_consequences > 0 or lexicon_passed
    if not has_consequences and len(content.strip()) > 100:
        flags.append({
            "level": "WARNING",
            "type": "NO_VISIBLE_CONSEQUENCES",
            "message": f"整章未检测到任何可见后果（传统：{total_consequences}处，叙事化：{lexicon_count}处）。"
        })
        suggestions.append(
            "让角色的行动产生可见、可触的后果——打破东西、留下痕迹、弄湿衣裳等。"
        )

    # ── 判定状态 ──
    status = "WARNING" if flags else "PASS"

    report = {
        "guard": "concrete_anchor_guard",
        "version": "v0.4.5",
        "status": status,
        "total_windows": window_analysis["total_windows"],
        "windows_with_object": window_analysis["windows_with_object"],
        "windows_with_body": window_analysis["windows_with_body"],
        "windows_with_scene": window_analysis["windows_with_scene"],
        "window_pass_rate": window_analysis["window_pass_rate"],
        "total_object_anchors": total_objects,
        "total_body_actions": total_body,
        "total_scene_anchors": total_scene,
        "total_visible_consequences": total_consequences,
        "missing_types": window_analysis["missing_types"],
        "metrics": {
            "visible_consequence_count": lexicon_count,
            "physical_count": lexicon_details["physical_count"],
            "object_count": lexicon_details["object_count"],
            "social_count": lexicon_details["social_count"],
            "rule_count": lexicon_details["rule_count"],
        },
        "flags": flags,
        "suggestions": suggestions,
        "hard_fail": False,
    }

    return report


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Concrete Anchor Guard — 具体锚点门禁"
    )
    parser.add_argument("--input", required=True, help="章节 TXT 文件")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--output", default=None, help="输出 report JSON 文件")
    args = parser.parse_args()

    content = Path(args.input).read_text(encoding="utf-8")
    report = run_concrete_anchor_check(content, args.chapter_no)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"\n[OK] Concrete anchor report saved: {args.output}")

    if report["status"] == "WARNING":
        print(f"\n[WARN] Concrete anchor: {len(report['flags'])} flags, "
              f"{len(report['suggestions'])} suggestions")
    else:
        print(f"\n[OK] Concrete anchor passed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
