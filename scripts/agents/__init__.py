#!/usr/bin/env python3
"""
Multi-Agent Review Board System v0.5.5

审稿团: 多Agent并行审稿, 只出报告不自动改正文.
Agent 基于启发式规则 (正则+规则) 做检测, 不调用外部 LLM.

Agents:
  context_agent    — 上一章承接/伤势延续/伏笔/真空续写
  voice_agent      — 角色口吻/方言浓度/梗语言包
  anti_ai_agent    — AI腔/总结腔/模板句/水文
  plot_agent       — 剧情推进/冲突/爽点/结尾压力
  continuity_agent — 人物状态/物品/地点/任务线/伏笔
  reader_pull_agent— 钩子/微兑现/新问题/追读力
  setting_agent    — 修仙设定自洽/物理类比/前后矛盾规则
  chief_editor     — 汇总去重排序, 输出 must_fix/should_fix/keep
  orchestrator     — 调度运行, 支持 light/full 模式
"""

from .base_agent import BaseAgent
from .context_agent import ContextAgent
from .voice_agent import VoiceAgent
from .anti_ai_agent import AntiAIAgent
from .plot_agent import PlotAgent
from .continuity_agent import ContinuityAgent
from .reader_pull_agent import ReaderPullAgent
from .setting_agent import SettingAgent
from .chief_editor import ChiefEditor
from .orchestrator import AgentOrchestrator, run_agent_review

__version__ = "0.5.5"
__all__ = [
    "BaseAgent",
    "ContextAgent", "VoiceAgent", "AntiAIAgent",
    "PlotAgent", "ContinuityAgent", "ReaderPullAgent",
    "SettingAgent", "ChiefEditor",
    "AgentOrchestrator", "run_agent_review",
]
