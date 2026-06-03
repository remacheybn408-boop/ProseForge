# Novel Forge — CLAUDE.md

## 项目概述
AI 长篇小说工程化写作流水线。CLI 入口 `novel.py`，代码位于 `src/cli/`（命令实现）和 `src/guards/`（门禁规则），核心逻辑在 `scripts/`。

## 关键结构
```
novel.py              ← CLI 入口（纯分发器，310行）
src/cli/
  shared.py           ← 共用 helpers（路径、配置加载）
  commands_core.py    ← 核心命令（demo/check/init/write/report/agents...）
  commands_db.py      ← DB 工作区管理
  commands_outline.py ← 大纲管理
  commands_menu.py    ← 菜单/帮助
  commands_status.py  ← 状态诊断
src/guards/           ← 21 个门禁规则模块
scripts/              ← 流水线核心逻辑
  agents/             ← 18 个 Agent 陪审团
tests/                ← pytest 测试
```

## 常用命令
```bash
python novel.py                    # 显示帮助
python novel.py status             # 环境诊断
python novel.py demo               # 跑全流程演示
python novel.py guards             # 列出所有 guard
python novel.py agents review 1    # 审稿第1章
python novel.py agents review 1 --mode full  # 完整审稿（18 Agent）
python novel.py stability-check --full  # 发布验收
pytest tests/ -q                   # 跑测试
```

## 关键约定
- **无引号文学写作**：小说正文对话融入叙述，禁用任何引号
- **risk_score**：0-100，越高表示问题越多（质量越差）
- **破折号限制**：≤5/千字，超过 WARN，>12 拦截
- **v0.6.5**：当前版本
- **代码规范**：继承 BaseAgent 实现 Agent，guard 通过 guard_registry 注册

## 发布验收标准
`python novel.py stability-check --full` 必须全部通过：
1. 版本号一致
2. pytest 296 passed
3. demo 全流程不报 ModuleNotFoundError
4. workspace + DB 完整
5. 21 个 guard 可加载
6. 18 Agent + Chief Editor 可运行
