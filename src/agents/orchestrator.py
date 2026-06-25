#!/usr/bin/env python3
"""Multi-agent review orchestrator."""

import json
import time
from pathlib import Path

from version import get_version

from .character import CharacterAgent
from .chief_editor_agent import ChiefEditor
from .continuity import ContinuityAgent
from .detail import DetailAgent
from .plot import PlotAgent
from .prose import ProseAgent
from .reader import ReaderAgent


_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # repo 根，与 pre.py / task_card_builder 读取锚点一致


AGENT_REGISTRY = {
    "continuity": ContinuityAgent,
    "character": CharacterAgent,
    "prose": ProseAgent,
    "plot": PlotAgent,
    "reader": ReaderAgent,
    "detail": DetailAgent,
}

# light vs full **不是质量等级差异**，只是参与审稿的 agent 子集差异：
#   - light：3 个 agent（continuity / prose / plot）—— 适合快速过一遍主链路
#   - full：6 个 agent（额外加 character / reader / detail）—— 完整审稿
# 两种模式所用每个 agent 内部的阈值、判定逻辑完全相同；区别只在"跑哪几位 agent"。
# CLI 入口（plugin 的 --mode light|full）已沿用此命名，重命名会破坏外部脚本，故保留。
MODE_AGENTS = {
    "light": ["continuity", "prose", "plot"],
    "full": ["continuity", "character", "prose", "plot", "reader", "detail"],
}


class AgentOrchestrator:
    """Orchestrates merged review agents and ChiefEditor."""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.agent_configs = self.config.get("agents", {})
        # 默认锚定 repo 根的绝对路径，避免不传 config 的调用方（plugins/CLI）按 CWD 落盘
        # 与读取方错位；显式传入的 output_dir 仍优先。
        self.output_dir = self.config.get("output_dir") or str(_PROJECT_ROOT / "reports" / "agent_reviews")
        self.mode = self.config.get("mode", "light")

    def run(self, content: str, chapter_no: int = 0, mode: str = "light", context: dict = None) -> dict:
        """执行多 Agent 审读。

        mode = "light" 跑 3 个 agent，mode = "full" 跑 6 个——参见模块顶部 MODE_AGENTS 注释，
        这是 agent 子集差异，不是质量阈值差异。
        """
        context = context or {}
        mode = mode or self.mode
        agent_names = MODE_AGENTS.get(mode, MODE_AGENTS["light"])

        agents = []
        for name in agent_names:
            agent_cls = AGENT_REGISTRY.get(name)
            if agent_cls is None:
                continue
            agent_cfg = self.agent_configs.get(name, {})
            agents.append(agent_cls(config=agent_cfg))

        agent_results = []
        for agent in agents:
            try:
                result = agent.review(content, chapter_no, context)
                result["chapter"] = chapter_no
                agent_results.append(result)
            except Exception as exc:
                agent_results.append(
                    {
                        "agent": agent.name,
                        "chapter": chapter_no,
                        "score": 100,
                        "status": "FAIL",
                        "findings": [
                            {
                                "level": "FAIL",
                                "message": f"Agent执行异常: {exc}",
                                "evidence": "",
                                "suggestion": "检查 Agent 实现",
                                "source": agent.name,
                            }
                        ],
                        "error": str(exc),
                    }
                )

        chief_cfg = self.agent_configs.get("chief_editor", {})
        chief = ChiefEditor(config=chief_cfg)
        chief_result = chief.review(content, chapter_no, {"agent_results": agent_results})

        agent_statuses = [result.get("status", "PASS") for result in agent_results]
        agent_scores = [result.get("score", 0) for result in agent_results]
        fail_count = sum(1 for status in agent_statuses if status == "FAIL")
        warn_count = sum(1 for status in agent_statuses if status == "WARNING")

        if fail_count > 0:
            overall_status = "FAIL"
        elif warn_count >= 3:
            overall_status = "WARNING"
        else:
            overall_status = "PASS"

        overall_score = int(sum(agent_scores) / max(1, len(agent_scores)))
        report = {
            "chapter": chapter_no,
            "mode": mode,
            "overall_score": overall_score,
            # overall_score 是"问题分"：越高问题越多、质量越差。消费方据此判断方向。
            "score_direction": "lower_is_better",
            "status": overall_status,
            "agents": agent_results,
            "chief_editor": chief_result,
            "summary": {
                "total_agents": len(agents),
                "pass_count": sum(1 for status in agent_statuses if status == "PASS"),
                "warn_count": warn_count,
                "fail_count": fail_count,
                "must_fix_count": chief_result.get("summary", {}).get("must_fix_count", 0),
                "should_fix_count": chief_result.get("summary", {}).get("should_fix_count", 0),
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "version": get_version(),
        }

        self._save_report(chapter_no, report)
        return report

    def _save_report(self, chapter_no: int, report: dict):
        try:
            output_path = Path(self.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            filename = f"chapter_{chapter_no:03d}_agent_review.json"
            filepath = output_path / filename
            filepath.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            report["_report_path"] = str(filepath)
        except Exception as exc:
            report["_report_error"] = str(exc)


def run_agent_review(
    content: str,
    chapter_no: int = 0,
    mode: str = "light",
    context: dict = None,
    config: dict = None,
) -> dict:
    orchestrator = AgentOrchestrator(config=config)
    return orchestrator.run(content, chapter_no, mode, context)
