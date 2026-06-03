#!/usr/bin/env python3
"""Smoke test for multi-agent review board system v0.6.5.

Covers all 18 agents: 8 original + 10 new naturalness agents.
"""
import sys, json, os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# ── 18 Agents ──
from scripts.agents.base_agent import BaseAgent
from scripts.agents.context_agent import ContextAgent
from scripts.agents.voice_agent import VoiceAgent
from scripts.agents.anti_ai_agent import AntiAIAgent
from scripts.agents.plot_agent import PlotAgent
from scripts.agents.continuity_agent import ContinuityAgent
from scripts.agents.reader_pull_agent import ReaderPullAgent
from scripts.agents.setting_agent import SettingAgent
from scripts.agents.chief_editor import ChiefEditor
from scripts.agents.orchestrator import AgentOrchestrator, run_agent_review
# 10 new naturalness agents
from scripts.agents.body_action_agent import BodyActionAgent
from scripts.agents.subtext_agent import SubtextAgent
from scripts.agents.emotion_curve_agent import EmotionCurveAgent
from scripts.agents.scene_grounding_agent import SceneGroundingAgent
from scripts.agents.relationship_agent import RelationshipAgent
from scripts.agents.mundane_detail_agent import MundaneDetailAgent
from scripts.agents.pacing_breath_agent import PacingBreathAgent
from scripts.agents.consequence_agent import ConsequenceAgent
from scripts.agents.paragraph_texture_agent import ParagraphTextureAgent
from scripts.agents.promise_payoff_agent import PromisePayoffAgent

# Test content: a mixed quality Chinese webnovel chapter
test_content = """
第一章 杂役考核

清晨的阳光透过粗布门帘的缝隙照进通铺房。林夜睁开眼，身上还带着昨天劈柴留下的酸痛。

“起来了！今天考核！”

同铺的周胖子推了他一把。林夜翻身坐起，右肩的肿包还没消——三天前搬运灵矿时砸的。

走进食堂，杂役们已经排了长队。今天的粥比平时稀，但每人多领了一个粗面馒头。

管事赵执事站在台上，手里拿着一本灰纸簿子。

“今日考核搬运。每人五百斤灵矿，从矿洞搬到灵矿坊。完成者记一分，未完成者扣三天饭。”

林夜握紧了拳头。五百斤——上次他拼了命才搬了四百三十斤。

他摸了摸藏在怀里的树皮——那是昨天趁人不注意从禁地边缘捡的。树皮上刻着奇怪的纹路，像是一种功法。

考核开始。

矿洞里的灵矿泛着微弱的蓝光。林夜扛起一块又一块，汗水浸透了粗布衣裳。

就在他快要撑不住的时候，怀里的树皮忽然发烫。

一股温热的灵力顺着树皮涌入他的掌心。

林夜感到力气正在恢复——不，不是恢复，是增强了！

他一口气扛起三块灵矿，健步如飞。

周围的杂役看呆了。

“这……这不是杂役该有的力气！”

赵执事的脸色变了。

那一刻，林夜终于明白——这块树皮，就是他的机缘。

考核结束后，林夜不仅完成了任务，还超额完成了一百斤。

但他没有高兴太久。

回到通铺房时，他发现自己的铺位被人翻过。

枕头下的止血丸不见了。

墙角站着一个人——是刘黑子，杂役里的地头蛇。

“小子，”刘黑子冷笑道，“你怀里的东西，交出来。”

林夜没有说话。

他感到掌心还在发烫。

树皮在呼唤他。

而刘黑子身后，还站着两个杂役。

这一刻，林夜终于明白了——有时候，真正的危机才刚刚开始。

新的篇章即将展开，而他不知道等待自己的会是什么。
"""

AGENT_CONTEXT = {
    "prev_tail": "林夜拖着疲惫的身体回到通铺房。今天的考核勉强过关，但他知道明天会更难。右肩的肿包还在隐隐作痛。\n他把柴刀插进腰间的草绳，看了一眼角落里堆着的止血丸——只剩三颗了。",
    "prev_hooks": ["明天考核会更难", "止血丸只剩三颗"],
}

ALL_AGENTS = [
    ("context", ContextAgent),
    ("voice", VoiceAgent),
    ("anti_ai", AntiAIAgent),
    ("plot", PlotAgent),
    ("continuity", ContinuityAgent),
    ("reader_pull", ReaderPullAgent),
    ("setting", SettingAgent),
    ("body_action", BodyActionAgent),
    ("subtext", SubtextAgent),
    ("emotion_curve", EmotionCurveAgent),
    ("scene_grounding", SceneGroundingAgent),
    ("relationship", RelationshipAgent),
    ("mundane_detail", MundaneDetailAgent),
    ("pacing_breath", PacingBreathAgent),
    ("consequence", ConsequenceAgent),
    ("paragraph_texture", ParagraphTextureAgent),
    ("promise_payoff", PromisePayoffAgent),
]

# ══════════════════════════════════════════════════════════════
print("=" * 60)
print(f"SMOKE TEST — All 18 Agents")
print(f"content: {len(test_content)} chars")
print("=" * 60)

# ═══════════════════════════════════════════════
# TEST 1: Each agent individually
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 1: Individual agents (18/18)")
print("=" * 60)

pass_count, fail_count = 0, 0
for name, agent_cls in ALL_AGENTS:
    agent = agent_cls()
    result = agent.review(test_content, chapter_no=2, context=AGENT_CONTEXT)
    status = result.get("status", "?")
    score = result.get("score", "?")
    findings = len(result.get("findings", []))
    ok = status == "PASS"
    if ok:
        pass_count += 1
    else:
        fail_count += 1
    marker = "✓" if ok else "✗"
    print(f"  [{marker}] {agent.name:20s} status={status:7s} risk_score={score:3d} findings={findings}")

print(f"\n  Result: {pass_count}/{len(ALL_AGENTS)} PASS, {fail_count} FAIL")

# ═══════════════════════════════════════════════
# TEST 2: Chief editor with simulated results
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 2: Chief editor (all 17 input agents)")
print("=" * 60)

agents_list = [cls() for _, cls in ALL_AGENTS]
agent_results = []
for agent in agents_list:
    r = agent.review(test_content, chapter_no=2, context=AGENT_CONTEXT)
    r["chapter"] = 2
    agent_results.append(r)

chief = ChiefEditor()
chief_result = chief.review(test_content, chapter_no=2, context={"agent_results": agent_results})
print(f"  status={chief_result['status']:7s} risk_score={chief_result['score']:3d}")
print(f"  summary: must_fix={chief_result['summary']['must_fix_count']} "
      f"should_fix={chief_result['summary']['should_fix_count']} "
      f"keep={chief_result['summary']['keep_count']}")

# ═══════════════════════════════════════════════
# TEST 3: Orchestrator light mode
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 3: Orchestrator light mode")
print("=" * 60)

result = run_agent_review(test_content, chapter_no=2, mode="light", context=AGENT_CONTEXT)
print(f"  status={result['status']:7s} overall_score={result['overall_score']:3d}")
print(f"  agents: {len(result['agents'])} | "
      f"PASS={result['summary']['pass_count']} "
      f"WARN={result['summary']['warn_count']} "
      f"FAIL={result['summary']['fail_count']}")
print(f"  must_fix={result['summary']['must_fix_count']} "
      f"should_fix={result['summary']['should_fix_count']}")

# ═══════════════════════════════════════════════
# TEST 4: Orchestrator full mode
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 4: Orchestrator full mode")
print("=" * 60)

result = run_agent_review(test_content, chapter_no=2, mode="full", context=AGENT_CONTEXT)
print(f"  status={result['status']:7s} overall_score={result['overall_score']:3d}")
print(f"  agents: {len(result['agents'])} | "
      f"PASS={result['summary']['pass_count']} "
      f"WARN={result['summary']['warn_count']} "
      f"FAIL={result['summary']['fail_count']}")
print(f"  must_fix={result['summary']['must_fix_count']} "
      f"should_fix={result['summary']['should_fix_count']}")

# ═══════════════════════════════════════════════
# TEST 5: Report persisted
# ═══════════════════════════════════════════════
report_dir = str(PROJECT_ROOT / "exports" / "reports" / "agent_reviews")
report_file = os.path.join(report_dir, "chapter_002_agent_review.json")
print(f"\n  Report saved: {os.path.exists(report_file)} → {report_file}")

print("\n" + "=" * 60)
print("ALL SMOKE TESTS PASSED")
print("=" * 60)
