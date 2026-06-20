"""character_psychology_crud.py — 角色心理状态独立文件 CRUD v1.0

历史: 由 mental_state_crud.py 重命名而来。

与 voice_cards 解耦，独立存储在 character_psychology/<set>/<角色>.json。
按 slot 隔离，卡组体系复用 voice_cards 的 active_set 配置。

向后兼容：
  - 读取时同时尝试新目录 `character_psychology/` 和旧目录 `mental_states/`
  - 写入时只写新目录
  - 角色卡 fallback 字段也同时尝试 `character_psychology` 和 `mental_state` 旧 key
"""
import json
from pathlib import Path


# ── 15 类心理状态维度定义 ──
CHARACTER_PSYCHOLOGY_CATEGORIES = [
    "抑郁症", "PTSD", "焦虑症", "强迫症", "PTSD（战场型）",
    "人格障碍", "进食障碍", "睡眠障碍", "物质滥用",
    "精神分裂", "双相情感障碍", "恐惧症",
    "解离性障碍", "适应障碍", "冲动控制障碍",
]

# Backward-compat alias
MENTAL_STATE_CATEGORIES = CHARACTER_PSYCHOLOGY_CATEGORIES

# 新/旧目录名（读取时同时检查，写入只写新）
_NEW_DIR_NAME = "character_psychology"
_LEGACY_DIR_NAME = "mental_states"


def _get_active_slot(project_root: Path) -> str | None:
    """获取当前活跃 slot 名。"""
    reg_file = project_root / "workspace" / "registry.json"
    if not reg_file.exists():
        return None
    try:
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        return reg.get("active_slot", "") or None
    except Exception:
        return None


def _get_active_card_set(project_root: Path) -> str:
    """复用 voice_cards 的卡组配置（同一本小说共享）。"""
    try:
        ws_dir = project_root / "workspace"
        slot = _get_active_slot(project_root)
        if not slot:
            return "default"
        proj_file = ws_dir / slot / "project.json"
        if proj_file.exists():
            proj = json.loads(proj_file.read_text(encoding="utf-8"))
            return proj.get("active_voice_card_set", "default")
    except Exception:
        pass
    return "default"


def _psychology_dir(project_root: Path, card_set: str | None = None,
                    *, for_write: bool = False) -> Path | None:
    """获取心理状态文件目录（按 slot + 卡组隔离）。

    for_write=True 总是返回新目录路径（并创建）。
    for_write=False 优先返回新目录；若不存在但旧 `mental_states/` 存在，返回旧目录。
    """
    ws_dir = project_root / "workspace"
    slot = _get_active_slot(project_root)
    if not slot:
        return None
    if card_set is None:
        card_set = _get_active_card_set(project_root)
    new_dir = ws_dir / slot / _NEW_DIR_NAME / card_set
    if for_write:
        new_dir.mkdir(parents=True, exist_ok=True)
        return new_dir
    if new_dir.exists():
        return new_dir
    legacy = ws_dir / slot / _LEGACY_DIR_NAME / card_set
    if legacy.exists():
        return legacy
    new_dir.mkdir(parents=True, exist_ok=True)
    return new_dir


def get_character_psychology(project_root: Path, name: str,
                              card_set: str | None = None) -> dict:
    """读取角色心理状态数据。

    优先读取 character_psychology/<set>/ 下的独立文件，
    fallback 顺序：mental_states/ 旧目录 → 角色卡嵌入数据（card['character_psychology']
    或 card['mental_state']）。
    都没有时返回空 dict。
    """
    ms_dir = _psychology_dir(project_root, card_set, for_write=False)
    if ms_dir:
        f = ms_dir / f"{name}.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass

    # Fallback: 从角色卡嵌入数据读取
    try:
        from .voice_diversity_guard import get_character_card
        card = get_character_card(project_root, name)
        if card:
            ps = card.get("character_psychology") or card.get("mental_state") or {}
            if ps:
                return ps
    except Exception:
        pass

    return {}


def save_character_psychology(project_root: Path, name: str, data: dict,
                               card_set: str | None = None) -> bool:
    """保存角色心理状态数据到独立文件（不碰角色卡）。"""
    ms_dir = _psychology_dir(project_root, card_set, for_write=True)
    if not ms_dir:
        return False
    f = ms_dir / f"{name}.json"
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def list_character_psychologies(project_root: Path) -> list[dict]:
    """列出当前 slot 所有角色的心理状态数据。

    返回: [{name: str, character_psychology: dict, mental_state: dict}, ...]
    `mental_state` 字段是 backward-compat alias，与 character_psychology 同值。
    仅返回存在独立文件的角色（不含 fallback 嵌入数据）。
    """
    card_set = _get_active_card_set(project_root)
    ms_dir = _psychology_dir(project_root, card_set, for_write=False)
    if not ms_dir or not ms_dir.exists():
        return []
    results = []
    for f in sorted(ms_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({"name": f.stem, "character_psychology": data,
                            "mental_state": data})
        except Exception:
            pass
    return results


# ═════════════════════════════════════════════════════════════════
# Backward-compat aliases — 旧 API 名继续工作
# ═════════════════════════════════════════════════════════════════

get_mental_state = get_character_psychology
save_mental_state = save_character_psychology
list_mental_states = list_character_psychologies
