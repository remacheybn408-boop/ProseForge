# Multi-Agent Review Board (v0.6.5 — 18 Agents)

18 个专业 Agent + 1 个 Chief Editor 并行审稿：

**核心 7 Agent（v0.5.5）：**
- **anti_ai_agent.py** — AI腔检测
- **context_agent.py** — 上下文承接
- **voice_agent.py** — 角色口吻
- **plot_agent.py** — 剧情推进
- **continuity_agent.py** — 前后连续性
- **reader_pull_agent.py** — 追读力
- **setting_agent.py** — 世界观设定

**新增 10 自然度 Agent（v0.6.5）：**
- **body_action_agent.py** — 动作自然度（避免站桩对话）
- **subtext_agent.py** — 潜台词（避免对话太直白）
- **emotion_curve_agent.py** — 情绪递进（避免跳跃太快）
- **scene_grounding_agent.py** — 场景落地（避免白房间写作）
- **relationship_agent.py** — 人物关系变化
- **mundane_detail_agent.py** — 生活烟火气
- **pacing_breath_agent.py** — 章节节奏呼吸
- **consequence_agent.py** — 代价后果
- **paragraph_texture_agent.py** — 段落质感（避免AI整齐句式）
- **promise_payoff_agent.py** — 伏笔兑现

**基础设施：**
- **chief_editor.py** — 总编汇总（去重、排序、分类）
- **orchestrator.py** — 调度编排

## 使用方式

```bash
# 轻量审稿（6 Agent 快速扫描）
python novel.py agents review <章节号>

# 完整审稿（18 Agent 并行）
python novel.py agents review <章节号> --mode full
```

## 设计原则

- **只审稿，不覆盖正文**：所有审稿结果输出报告，作者决定是否采纳
- **默认关闭**：不影响主流水线，手动触发
- **多维度并行**：18 个视角同时审稿，避免单视角盲区
- **两套体系**：Agent 陪审团（18 个启发式规则Agent）与 Guard 门禁（21 个精确规则）互补——Guard 拦截硬性问题（幻觉/连续性/破折号），Agent 评估软性质量（自然度/节奏/关系）

## 模式说明

| 模式 | Agent 数 | 适用场景 |
|------|----------|----------|
| light | 6 | 日常快速检查（核心 + 动作/场景） |
| full | 18 | 发布前全面审查 |
