"""voice_diversity_guard.py — 角色声纹检测 v0.6.6

检查同一本小说里不同角色的说话方式是否过于雷同。
声纹卡按 slot 独立存储，不窜库。
"""
import re
import json
from pathlib import Path
from collections import Counter


# ── 声纹卡字段定义 ──
VOICE_CARD_FIELDS = [
    "sentence_length_preference",
    "dialect",                     # 方言特征
    "dialect_words",               # 特色方言词
    "common_words",
    "forbidden_words",
    "emotional_leak_style",
    "anger_style",
    "lie_style",
    "silence_style",
    "humor_style",
    "relationship_specific_tone",
]


def get_voice_cards_dir(project_root: Path) -> Path:
    """获取当前活跃 slot 的声纹卡目录."""
    try:
        ws_dir = project_root / "workspace"
        reg_file = ws_dir / "registry.json"
        if not reg_file.exists():
            return None
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return None
        vc_dir = ws_dir / active / "voice_cards"
        vc_dir.mkdir(parents=True, exist_ok=True)
        return vc_dir
    except Exception:
        return None


def list_voice_cards(project_root: Path) -> list[dict]:
    """列出当前 slot 所有声纹卡."""
    vc_dir = get_voice_cards_dir(project_root)
    if not vc_dir or not vc_dir.exists():
        return []
    cards = []
    for f in sorted(vc_dir.glob("*.json")):
        try:
            card = json.loads(f.read_text(encoding="utf-8"))
            card["_file"] = f.name
            cards.append(card)
        except Exception:
            pass
    return cards


def get_voice_card(project_root: Path, name: str) -> dict | None:
    """获取单个角色声纹卡."""
    vc_dir = get_voice_cards_dir(project_root)
    if not vc_dir:
        return None
    f = vc_dir / f"{name}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return None


def save_voice_card(project_root: Path, name: str, card: dict) -> bool:
    """保存声纹卡到当前 slot."""
    vc_dir = get_voice_cards_dir(project_root)
    if not vc_dir:
        return False
    card["name"] = name
    f = vc_dir / f"{name}.json"
    f.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def delete_voice_card(project_root: Path, name: str) -> bool:
    """删除声纹卡."""
    vc_dir = get_voice_cards_dir(project_root)
    if not vc_dir:
        return False
    f = vc_dir / f"{name}.json"
    if f.exists():
        f.unlink()
        return True
    return False


def extract_dialogue_lines(text: str) -> list[dict]:
    """从文本中提取对话行及其上下文."""
    lines = []
    # 匹配引号内对话（含零引号写法中的人物说）
    for m in re.finditer(r'([\u4e00-\u9fff]{2,6}(?:说|问|答|道|喊|叫|骂|嘀咕|提醒|解释|承认|补充|打断))[：:，,。.]?\s*(.{2,60}?)(?=[，。。！？\n]|$)', text):
        speaker = m.group(1).rstrip("：:,，。.")
        content = m.group(2).strip()
        if len(content) >= 4:
            lines.append({"speaker": speaker, "content": content})
    return lines


def calc_sentence_stats(text: str) -> dict:
    """计算句长统计."""
    sentences = re.split(r'[。！？\n]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]
    if not sentences:
        return {"avg": 0, "std": 0, "short_ratio": 0, "long_ratio": 0, "count": 0}
    lengths = [len(s) for s in sentences]
    avg = sum(lengths) / len(lengths)
    variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
    std = variance ** 0.5
    short_count = sum(1 for l in lengths if l <= 8)
    long_count = sum(1 for l in lengths if l >= 40)
    return {
        "avg": round(avg, 1),
        "std": round(std, 1),
        "short_ratio": round(short_count / len(lengths), 3),
        "long_ratio": round(long_count / len(lengths), 3),
        "count": len(lengths),
    }


def run_voice_diversity_check(content: str, chapter_no: int,
                               project_root: Path) -> dict:
    """主检测入口：对比当前章节对话与声纹卡."""
    cards = list_voice_cards(project_root)
    findings = []

    if not cards:
        return {
            "guard": "voice_diversity_guard",
            "status": "PASS",
            "score": 100,
            "findings": [{"level": "INFO", "message": "暂无声纹卡，跳过检测"}],
            "chapter_no": chapter_no,
        }

    dialogues = extract_dialogue_lines(content)
    if not dialogues:
        return {
            "guard": "voice_diversity_guard",
            "status": "PASS",
            "score": 100,
            "chapter_no": chapter_no,
            "findings": [],
        }

    # 按说话人分组
    speaker_lines = {}
    for d in dialogues:
        spk = d["speaker"]
        if spk not in speaker_lines:
            speaker_lines[spk] = []
        speaker_lines[spk].append(d["content"])

    # 对每个有声纹卡的角色做检测
    card_map = {c.get("name", ""): c for c in cards}
    for spk, lines in speaker_lines.items():
        card = card_map.get(spk)
        if not card:
            continue

        # 0. 检查方言词覆盖
        dialect = card.get("dialect", "")
        dialect_words = card.get("dialect_words", [])
        if dialect_words:
            found_dialect = sum(1 for w in dialect_words for line in lines if w in line)
            if found_dialect == 0 and len(lines) >= 2:
                findings.append({
                    "level": "WARN",
                    "message": f"角色「{spk}」{dialect}特征丢失——未使用任何方言词",
                    "evidence": f"声纹卡标记方言词: {', '.join(dialect_words[:5])}",
                    "suggestion": f"在 {spk} 的对话中自然嵌入方言词",
                })

        # 1. 检查禁用词
        forbidden = card.get("forbidden_words", [])
        for fw in forbidden:
            for line in lines:
                if fw in line:
                    findings.append({
                        "level": "WARN",
                        "message": f"角色「{spk}」说了不应说的词「{fw}」",
                        "evidence": line[:60],
                        "suggestion": f"声纹卡标记 {spk} 不会说这个词",
                    })

        # 2. 检查常用词覆盖
        common = card.get("common_words", [])
        if common:
            found_common = sum(1 for w in common for line in lines if w in line)
            if found_common == 0 and len(lines) >= 2:
                findings.append({
                    "level": "WARN",
                    "message": f"角色「{spk}」的对话未使用任何习惯用语",
                    "evidence": f"常用词: {', '.join(common[:5])}",
                    "suggestion": f"让 {spk} 在对话中自然使用习惯用语",
                })

        # 3. 检查句长偏好
        pref = card.get("sentence_length_preference", "")
        stats = calc_sentence_stats("。".join(lines))
        if pref == "短句" and stats["avg"] > 20:
            findings.append({
                "level": "WARN",
                "message": f"角色「{spk}」应为短句偏好，实际平均句长 {stats['avg']}",
                "evidence": f"声纹卡标记 {spk} 说短句",
                "suggestion": f"将 {spk} 的对话拆短",
            })
        elif pref == "长句" and stats["avg"] < 12:
            findings.append({
                "level": "WARN",
                "message": f"角色「{spk}」应为长句偏好，实际平均句长 {stats['avg']}",
                "evidence": f"声纹卡标记 {spk} 说长句",
                "suggestion": f"让 {spk} 的对话更完整、更绕",
            })

    # 综合评分
    score = max(0, 100 - len(findings) * 15)
    status = "PASS"
    if len(findings) >= 3:
        status = "WARNING"
    elif len(findings) >= 5:
        status = "FAIL"

    return {
        "guard": "voice_diversity_guard",
        "status": status,
        "score": score,
        "findings": findings,
        "chapter_no": chapter_no,
    }
