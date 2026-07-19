"""聊天上下文编译（V2-002）。

把分支历史 + persona + 项目大纲摘要 + pinned story-bible 条目编译成一次
生成所用的 system blocks / messages，并按模型 context 预算裁剪历史
（最旧先丢）。每次执行持久化一条不可变 ContextSnapshot（blocks +
injected ids + omitted reasons），供 message.model_snapshot_json 关联。

V2-005 会在此之上加 trigger 注入：`collect_fact_blocks` 是预留的 seam，
签名保持稳定，内部从 pinned-only 扩展为 pinned + triggered。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from proseforge.application.context.build_snapshot import BuildContextSnapshot
from proseforge.context_engine.budgeting import calculate_budget
from proseforge.context_engine.tokenizer import ConservativeTokenizer
from proseforge.infrastructure.database.models.story_bible import StoryBibleEntryModel

DEFAULT_PERSONA = (
    "You are ProseForge's fiction writing copilot. Answer in the user's "
    "language, stay consistent with the project outline and the pinned "
    "story facts below, and never contradict established canon."
)


@dataclass(frozen=True)
class ChatContext:
    system_blocks: tuple[dict, ...]          # persona + pinned/triggered facts + omitted 摘要
    messages: tuple[dict, ...]               # 全分支历史裁剪后 [{"role","text"},...]
    snapshot_id: str                         # 已持久化 ContextSnapshot id
    injected_fact_ids: tuple[str, ...]       # 本次注入的 story bible 条目 id
    model_snapshot: dict                     # {provider,model,context_window,max_output_tokens,source}
    reasoning_snapshot: dict                 # {level,parameter,strength,provider_parameter,warnings} 或 {level,supported:False,reason}


class CompileChatContext:
    """按项目 + 分支历史 + 模型能力编译一次聊天生成的上下文。"""

    def __init__(self, uow, tokenizer=None):
        self.uow = uow
        self.tokenizer = tokenizer or ConservativeTokenizer()
        self.snapshot_builder = BuildContextSnapshot(self.tokenizer)

    async def execute(self, *, project_id: str, history, capabilities, provider: str, model: str, reasoning: dict, user_id: str = "") -> ChatContext:
        budget = calculate_budget(capabilities.context_window, capabilities.max_output_tokens)
        system_blocks: list[dict[str, Any]] = [self.snapshot_builder.describe_block(block_type="persona", source_id="default", text=DEFAULT_PERSONA, priority=100)]
        outline_summary = await self._outline_summary(project_id, user_id)
        if outline_summary:
            system_blocks.append(self.snapshot_builder.describe_block(block_type="outline", source_id="latest", text=outline_summary, priority=80))
        base_tokens = sum(int(block["token_estimate"]) for block in system_blocks)
        matching_text = "\n".join(message.content for message in history[-8:] if message.content)
        fact_blocks, injected_fact_ids, fact_omitted = await self.collect_fact_blocks(project_id, matching_text, max(0, budget.input_tokens - base_tokens))
        system_blocks.extend(fact_blocks)
        system_tokens = sum(self.tokenizer.count(str(block["text"])) for block in system_blocks)
        allowance = max(0, budget.input_tokens - system_tokens)
        kept, omitted = self._trim(history, allowance)
        if omitted:
            summary = f"{len(omitted)} earlier message(s) were omitted to fit the model context budget."
            system_blocks.append(self.snapshot_builder.describe_block(block_type="omitted", source_id="history", text=summary))
        snapshot_id = await self._persist_snapshot(project_id, system_blocks, kept, injected_fact_ids, [*fact_omitted, *omitted], budget)
        model_snapshot = {
            "provider": provider,
            "model": model,
            "context_window": capabilities.context_window,
            "max_output_tokens": capabilities.max_output_tokens,
            "source": capabilities.source,
            "context_snapshot_id": snapshot_id,
        }
        return ChatContext(
            system_blocks=tuple(system_blocks),
            messages=tuple({"role": message.role, "text": message.content} for message in kept),
            snapshot_id=snapshot_id,
            injected_fact_ids=tuple(injected_fact_ids),
            model_snapshot=model_snapshot,
            reasoning_snapshot=dict(reasoning),
        )

    async def collect_fact_blocks(self, project_id: str, matching_text: str, token_budget: int) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
        """常驻注入：pinned 且 active 的 story-bible 条目。

        V2-005 seam：trigger-word 注入将在此并入（pinned ∪ triggered）。
        """
        rows = (await self.uow.session.scalars(
            select(StoryBibleEntryModel)
            .where(StoryBibleEntryModel.project_id == project_id)
            .order_by(StoryBibleEntryModel.kind, StoryBibleEntryModel.key)
        )).all()
        selection = self.snapshot_builder.select_story_facts(rows, matching_text, token_budget)
        return list(selection.blocks), list(selection.injected_fact_ids), list(selection.omitted)

    async def _outline_summary(self, project_id: str, user_id: str) -> str:
        outlines = await self.uow.outlines.list_owned(project_id, user_id)
        if not outlines:
            return ""
        latest = outlines[-1]
        try:
            payload = json.loads(latest.payload or "{}")
        except (TypeError, ValueError):
            payload = {}
        raw = str(payload.get("raw_content") or "")[:500]
        summary = f"Outline: {latest.title}"
        if raw:
            summary = f"{summary}\n{raw}"
        return summary

    def _trim(self, history, allowance: int):
        kept: list = []
        omitted: list[dict[str, str]] = []
        used = 0
        for message in reversed(history):
            if not message.content:
                continue
            tokens = self.tokenizer.count(message.content)
            if kept and used + tokens > allowance:
                omitted.append({"source_type": "message", "source_id": message.id, "message_id": message.id, "reason": "budget_trim"})
                continue
            kept.append(message)
            used += tokens
        kept.reverse()
        omitted.reverse()
        return kept, omitted

    async def _persist_snapshot(self, project_id: str, system_blocks, kept, injected_fact_ids, omitted, budget) -> str:
        snapshot = self.snapshot_builder.persist(
            self.uow.session, project_id=project_id, blocks=list(system_blocks), messages=kept,
            injected_fact_ids=injected_fact_ids, omitted=omitted, budget=budget,
        )
        await self.uow.session.flush()
        return snapshot.id
