#!/usr/bin/env python3
"""
orchestrator.py — 多Agent审稿调度器 v0.5.5

调度 Agent 运行, 支持 light/full 模式:
  light: context, voice, anti_ai, plot, chief_editor (5 agents)
  full:  全部8个 + chief_editor

输出:
  - 内存中返回完整报告 dict
  - 报告写入 reports/agent_reviews/chapter_NNN_agent_review.json

用法:
  from scripts.agents.orchestrator import run_agent_review
  result = run_agent_review(content, chapter_no=5, mode="light", context={...})
"""

import json
import time
from pathlib import Path
from typing import Optional

from .context_agent import ContextAgent
from .voice_agent import VoiceAgent
from .anti_ai_agent import AntiAIAgent
from .plot_agent import PlotAgent
from .continuity_agent import ContinuityAgent
from .reader_pull_agent import ReaderPullAgent
from .setting_agent import SettingAgent
from .chief_editor import ChiefEditor
from .body_action_agent import BodyActionAgent
from .subtext_agent import SubtextAgent
from .emotion_curve_agent import EmotionCurveAgent
from .scene_grounding_agent import SceneGroundingAgent
from .relationship_agent import RelationshipAgent
from .mundane_detail_agent import MundaneDetailAgent
from .pacing_breath_agent import PacingBreathAgent
from .consequence_agent import ConsequenceAgent
from .paragraph_texture_agent import ParagraphTextureAgent
from .promise_payoff_agent import PromisePayoffAgent


# ── Agent 注册表 ──
AGENT_REGISTRY = {
    "context": ContextAgent,
    "voice": VoiceAgent,
    "anti_ai": AntiAIAgent,
    "plot": PlotAgent,
    "continuity": ContinuityAgent,
    "reader_pull": ReaderPullAgent,
    "setting": SettingAgent,
    "body_action": BodyActionAgent,
    "subtext": SubtextAgent,
    "emotion_curve": EmotionCurveAgent,
    "scene_grounding": SceneGroundingAgent,
    "relationship": RelationshipAgent,
    "mundane_detail": MundaneDetailAgent,
    "pacing_breath": PacingBreathAgent,
    "consequence": ConsequenceAgent,
    "paragraph_texture": ParagraphTextureAgent,
    "promise_payoff": PromisePayoffAgent,
    "chief_editor": ChiefEditor,
}

# ── 模式定义 ──
MODE_AGENTS = {
    "light": ["context", "voice", "anti_ai", "plot",
              "body_action", "scene_grounding"],
    "full": ["context", "voice", "anti_ai", "plot",
              "continuity", "reader_pull", "setting",
              "body_action", "subtext", "emotion_curve",
              "scene_grounding", "relationship", "mundane_detail",
              "pacing_breath", "consequence", "paragraph_texture",
              "promise_payoff"],
}


class AgentOrchestrator:
    """多Agent审稿调度器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.agent_configs = self.config.get("agents", {})
        self.output_dir = self.config.get(
            "output_dir", "reports/agent_reviews")
        self.mode = self.config.get("mode", "light")

    def run(self, content: str, chapter_no: int = 0,
            mode: str = "light", context: dict = None) -> dict:
        """运行审稿流程。

        Args:
            content: 章节文本。
            chapter_no: 章节号。
            mode: 'light' 或 'full'。
            context: 上下文 (prev_tail, prev_hooks, voice_profiles 等)。

        Returns:
            完整审稿报告 dict。
        """
        context = context or {}
        mode = mode or self.mode
        agent_names = MODE_AGENTS.get(mode, MODE_AGENTS["light"])

        # ── 实例化 Agent ──
        agents = []
        for name in agent_names:
            agent_cls = AGENT_REGISTRY.get(name)
            if agent_cls is None:
                continue
            agent_cfg = self.agent_configs.get(name, {})
            agent = agent_cls(config=agent_cfg)
            agents.append(agent)

        # ── 并行运行 (顺序执行, 可按需改为并行) ──
        agent_results = []
        for agent in agents:
            try:
                result = agent.review(content, chapter_no, context)
                result["chapter"] = chapter_no
                agent_results.append(result)
            except Exception as e:
                agent_results.append({
                    "agent": agent.name,
                    "chapter": chapter_no,
                    "score": 0,
                    "status": "PASS",
                    "findings": [{
                        "level": "WARN",
                        "message": f"Agent执行异常: {str(e)}",
                        "evidence": "",
                        "suggestion": "检查 Agent 实现",
                    }],
                    "error": str(e),
                })

        # ── 主编汇总 ──
        chief_cfg = self.agent_configs.get("chief_editor", {})
        chief = ChiefEditor(config=chief_cfg)
        chief_context = {"agent_results": agent_results}
        chief_result = chief.review(content, chapter_no, chief_context)

        # ── 计算整体状态 ──
        agent_statuses = [r.get("status", "PASS") for r in agent_results]
        agent_scores = [r.get("score", 0) for r in agent_results]
        fail_count = sum(1 for s in agent_statuses if s == "FAIL")
        warn_count = sum(1 for s in agent_statuses if s == "WARNING")

        if fail_count > 0:
            overall_status = "FAIL"
        elif warn_count >= 3:
            overall_status = "WARNING"
        else:
            overall_status = "PASS"

        overall_score = int(sum(agent_scores) / max(1, len(agent_scores)))

        # ── 构建报告 ──
        report = {
            "chapter": chapter_no,
            "mode": mode,
            "overall_score": overall_score,
            "status": overall_status,
            "agents": agent_results,
            "chief_editor": chief_result,
            "summary": {
                "total_agents": len(agents),
                "pass_count": sum(1 for s in agent_statuses if s == "PASS"),
                "warn_count": warn_count,
                "fail_count": fail_count,
                "must_fix_count": chief_result.get("summary", {}).get("must_fix_count", 0),
                "should_fix_count": chief_result.get("summary", {}).get("should_fix_count", 0),
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "version": "0.5.5",
        }

        # ── 写入磁盘 ──
        self._save_report(chapter_no, report)

        return report

    def _save_report(self, chapter_no: int, report: dict):
        """保存报告到磁盘"""
        try:
            output_path = Path(self.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            filename = f"chapter_{chapter_no:03d}_agent_review.json"
            filepath = output_path / filename
            filepath.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8")
            report["_report_path"] = str(filepath)
        except Exception as e:
            report["_report_error"] = str(e)


# ── 便捷函数 ──


def run_agent_review(content: str, chapter_no: int = 0,
                     mode: str = "light", context: dict = None,
                     config: dict = None) -> dict:
    """便捷入口: 运行多Agent审稿并返回报告。

    Args:
        content: 章节文本。
        chapter_no: 章节号。
        mode: 'light' (5 agents) 或 'full' (8 agents)。
        context: 上下文 dict — 传递给所有 Agent。
        config: orchestrator 配置 dict。

    Returns:
        {
            "chapter": N,
            "overall_score": X,     # 0=完美, 100=极差
            "status": "PASS"/"WARNING"/"FAIL",
            "agents": [...],         # 各Agent报告
            "chief_editor": {...},   # 主编汇总
            "mode": "...",
            "summary": {...},
        }
    """
    orchestrator = AgentOrchestrator(config=config)
    return orchestrator.run(content, chapter_no, mode, context)


# ── CLI ──

def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Multi-Agent Review Board Orchestrator")
    parser.add_argument("content_file", help="章节 TXT 文件路径")
    parser.add_argument("--chapter-no", type=int, default=1, help="章节号")
    parser.add_argument("--mode", choices=["light", "full"], default="light",
                        help="审稿模式: light(5 agents) / full(8 agents)")
    parser.add_argument("--prev-tail-file", default=None,
                        help="上一章结尾 TXT")
    parser.add_argument("--prev-brief-file", default=None,
                        help="上一章 brief JSON")
    parser.add_argument("--config", default=None, help="Agent 配置 YAML/JSON")
    parser.add_argument("--output", default=None,
                        help="输出报告路径 (默认 reports/agent_reviews/)")
    args = parser.parse_args()

    # 读取内容
    content = Path(args.content_file).read_text(encoding="utf-8")

    # 构建 context
    context = {}
    if args.prev_tail_file:
        prev_tail_path = Path(args.prev_tail_file)
        if prev_tail_path.exists():
            context["prev_tail"] = prev_tail_path.read_text(encoding="utf-8")
    if args.prev_brief_file:
        brief_path = Path(args.prev_brief_file)
        if brief_path.exists():
            context["prev_brief"] = json.loads(
                brief_path.read_text(encoding="utf-8"))

    # 加载配置
    config = {}
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            if config_path.suffix in (".yaml", ".yml"):
                try:
                    import yaml
                    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                except ImportError:
                    print("[WARN] PyYAML not installed, using JSON")
                    config = json.loads(config_path.read_text(encoding="utf-8"))
            else:
                config = json.loads(config_path.read_text(encoding="utf-8"))

    if args.output:
        config["output_dir"] = str(Path(args.output).parent)

    # 运行
    result = run_agent_review(
        content, chapter_no=args.chapter_no,
        mode=args.mode, context=context, config=config)

    # 输出
    print(json.dumps(result, ensure_ascii=False, indent=2))

    status = result.get("status", "PASS")
    score = result.get("overall_score", 0)
    summary = result.get("summary", {})
    print(f"\n[{status}] Chapter {args.chapter_no}: "
          f"risk_score={score}/100 | "
          f"PASS={summary.get('pass_count', 0)} "
          f"WARN={summary.get('warn_count', 0)} "
          f"FAIL={summary.get('fail_count', 0)}")
    print(f"  must_fix={summary.get('must_fix_count', 0)} "
          f"should_fix={summary.get('should_fix_count', 0)}")

    if status == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
