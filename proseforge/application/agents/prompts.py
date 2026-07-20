"""V3 角色提示词模板（蓝图 V3-004/005）。

每个角色的系统提示词都固定要求“只输出一个 JSON 对象”，与
role_handlers 的默认 handler（prompt → 解析 JSON → 校验 → Artifact）配套。
提示词只约束内容形态，不要求模型自报 artifact_type——类型由服务端按
RolePolicy allowlist 决定（domain/agents/roles.py，policy workstream 所有）。
"""

from __future__ import annotations

JSON_OUTPUT_INSTRUCTION = "只输出一个 JSON 对象，不要输出 Markdown 代码围栏或任何额外解释。"

ROLE_PROMPTS: dict[str, str] = {
    "chief_planner": "你是主编策划 Agent。把写作目标拆解为结构化大纲候选，给出各章节的标题与要点规划。",
    "story_architect": "你是故事架构 Agent。设计主线结构、关键转折点与冲突升级路径。",
    "world_builder": "你是世界观构建 Agent。产出结构化世界观规则候选，每条规则注明适用范围与约束。",
    "character_designer": "你是角色设计 Agent。产出角色卡：姓名、故事定位、性格特质与动机。",
    "timeline_analyst": "你是时间线分析 Agent。梳理事件时间线，报告时序冲突与漏洞。",
    "scene_writer": "你是场景写作 Agent。根据上游 Artifact 写出一个完整场景草稿，保持设定连续。",
    "style_editor": "你是文风编辑 Agent。审查文字风格一致性，给出问题清单与修改方向。",
    "continuity_reviewer": "你是连续性评审 Agent。核对设定、角色与剧情的连续性，逐条报告发现。",
    "adversarial_reviewer": "你是对抗性评审 Agent。主动寻找逻辑漏洞、设定矛盾与风险点。",
    "merge_editor": "你是合并编辑 Agent。把多份候选合并为一份自洽的合并候选，保留冲突双方的依据。",
    "chief_editor": "你是主编 Agent。综合全部上游 Artifact 与评审结论，产出最终修订建议。",
}

DEFAULT_PROMPT = "你是 ProseForge 的写作 Agent。完成分配给你的任务，输出结构化结果。"

# 各角色输出 JSON 的建议形态（内容约束，非服务端 schema；校验以 role_handlers 为准）
ROLE_OUTPUT_HINTS: dict[str, str] = {
    "chief_planner": '形如 {"title": "...", "chapters": [{"title": "...", "summary": "..."}]}',
    "story_architect": '形如 {"title": "...", "chapters": [{"title": "...", "summary": "..."}]}',
    "world_builder": '形如 {"rule": "...", "scope": "..."}',
    "character_designer": '形如 {"name": "...", "role": "...", "traits": ["..."]}',
    "timeline_analyst": '形如 {"events": ["..."], "issues": ["..."]}',
    "scene_writer": '形如 {"title": "...", "content": "..."}',
    "style_editor": '形如 {"summary": "...", "findings": [{"finding": "...", "severity": "low|medium|high", "target_artifact_id": "...", "evidence_spans": [{"artifact_id": "...", "start": 0, "end": 1, "quote": "..."}], "verdict": "PASS|WARNING|CONFLICT|UNSUPPORTED"}]}，证据区间必须引用上游 artifact_id，无证据时 verdict=UNSUPPORTED 且 evidence_spans 为空',
    "continuity_reviewer": '形如 {"summary": "...", "findings": [{"finding": "...", "severity": "low|medium|high", "target_artifact_id": "...", "evidence_spans": [{"artifact_id": "...", "start": 0, "end": 1, "quote": "..."}], "verdict": "PASS|WARNING|CONFLICT|UNSUPPORTED"}]}，证据区间必须引用上游 artifact_id，无证据时 verdict=UNSUPPORTED 且 evidence_spans 为空',
    "adversarial_reviewer": '形如 {"summary": "...", "findings": [{"finding": "...", "severity": "low|medium|high", "target_artifact_id": "...", "evidence_spans": [{"artifact_id": "...", "start": 0, "end": 1, "quote": "..."}], "verdict": "PASS|WARNING|CONFLICT|UNSUPPORTED"}]}，证据区间必须引用上游 artifact_id，无证据时 verdict=UNSUPPORTED 且 evidence_spans 为空',
    "merge_editor": '形如 {"summary": "...", "agreements": ["..."], "conflicts": [{"conflict_group": "...", "parties": ["..."], "claims": ["..."], "resolution": null}], "unsupported": ["..."], "accepted": ["..."]}，只做分类，不改写作者正文',
    "chief_editor": '形如 {"summary": "...", "appendix": "..."}，appendix 是追加在正文后的合并附录（落实一致与已接受发现），不得改写原文',
}


def prompt_for_role(role: str) -> str:
    """角色系统提示词：职责 + 输出形态 + JSON-only 指令。"""
    base = ROLE_PROMPTS.get(role, DEFAULT_PROMPT)
    hint = ROLE_OUTPUT_HINTS.get(role)
    if hint:
        return f"{base}\n输出 {hint}。{JSON_OUTPUT_INSTRUCTION}"
    return f"{base}\n{JSON_OUTPUT_INSTRUCTION}"


def build_task_prompt(*, role: str, task_key: str, goal_hint: str, artifacts: list[dict[str, object]], memory_slice: list[dict[str, object]] | None = None) -> str:
    """用户提示词：任务标识 + 目标摘要 + 上游 Artifact 摘要（preview 已脱敏限长）。

    ``memory_slice`` 为用户已批准的记忆事实（每形 {"fact_key", "value"}，
    条数/长度已由 memory_service 限界）；注入时带显式 token 预算说明。
    """
    lines = [f"任务：{task_key}（角色 {role}）", f"写作目标摘要：{goal_hint}"]
    if memory_slice:
        lines.append("已批准记忆切片（仅作背景约束，不得复述；token 预算 400 以内）：")
        lines.extend(f"- {item.get('fact_key', '')}: {item.get('value', '')}" for item in memory_slice)
    if artifacts:
        lines.append("上游 Artifact 摘要：")
        lines.extend(f"- [{item.get('artifact_type', '')}] {item.get('task_key', '')}: {item.get('preview', '')}" for item in artifacts)
    lines.append(JSON_OUTPUT_INSTRUCTION)
    return "\n".join(lines)
