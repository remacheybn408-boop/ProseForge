## Novel Forge

Python 项目，CLI 入口为 `novel.py`。命令实现全部在 `src/cli/`，guard 在 `src/guards/`。

### 关键文件
- `novel.py` — CLI 入口（短）
- `src/cli/commands_core.py` — 大部分命令实现
- `src/cli/shared.py` — 共用路径和配置加载
- `src/guards/` — 23 个门禁规则模块
- `scripts/agents/` — 18 Agent 陪审团
- `scripts/guard_registry.py` — 门禁注册中心

### 常用命令
- `python novel.py status` — 诊断
- `python novel.py demo` — 全流程
- `python novel.py stability-check --full` — 验收
- `pytest tests/ -q` — 测试

### 编程约定
- 新 guard：在 `src/guards/` 下创建，用 `guard_registry.py` 注册
- 新 Agent：在 `scripts/agents/` 下创建，继承 `BaseAgent`，在 `orchestrator.py` 注册
- 字符串用单引号，中文字符串例外
- 版本号在 `VERSION` 文件（唯一来源）
