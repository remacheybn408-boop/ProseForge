## Novel Forge

Python 项目，Hermes Plugin 工具集。命令实现全部在 `src/`，guard 在 `src/guards/`。

### 关键文件
- HermesForgeN — Hermes Plugin 12 工具
- `src/bios.py` — 插件调度入口（pre/post/batch/volume）
- `src/pipeline/` — 全流程实现（`pre.py` / `post.py` / `ingest.py` 等）
- `src/pipeline/_base.py` — 共用路径与配置加载（`load_config` 等）
- `src/utils/config_utils.py` — 配置 schema 归一化（`normalize_config`）
- `src/guards/` — 门禁规则模块
- `src/guards/guard_registry.py` — 门禁注册中心
- `src/agents/` — Agent 陪审团
- `src/agents/orchestrator.py` — Agent 调度与注册中心

### 常用命令
- `nf_状态` — 诊断
- `nf_预写/续写` — 全流程
- `nf_审稿` — 验收
- `pytest tests/ -q` — 测试

### 编程约定
- 新 guard：在 `src/guards/` 下创建，用 `guard_registry.py` 注册
- 新 Agent：在 `src/agents/` 下创建，继承 `BaseAgent`，在 `src/agents/orchestrator.py` 注册
- 字符串用单引号，中文字符串例外
- 版本号在 `VERSION` 文件（唯一来源）
