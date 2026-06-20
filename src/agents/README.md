# Multi-Agent Review Board

6 个合并审稿 Agent + 1 个 Chief Editor：

- `continuity.py`: 上下文承接 + 连续性
- `character.py`: 口吻 + 心理 + 关系
- `prose.py`: 反 AI 腔 + 段落质感 + 潜台词 + 设定自洽
- `plot.py`: 剧情推进 + 节奏呼吸 + 承诺兑现 + 代价后果
- `reader.py`: 追读力 + 情绪递进
- `detail.py`: 动作自然度 + 场景落地 + 生活细节

基础设施：

- `base_agent.py`
- `chief_editor_agent.py`
- `orchestrator.py`

模式：

- `light`: `continuity / prose / plot`
- `full`: `continuity / character / prose / plot / reader / detail`
