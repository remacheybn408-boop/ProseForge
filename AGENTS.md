# Novel Forge — AGENTS.md

## 项目身份
AI 辅助长篇小说写作流水线。代码全在本地，不依赖外部 API。

## 项目结构
```
novel.py                ← CLI 入口
src/cli/                ← 命令实现
src/guards/             ← 21 个门禁规则
scripts/                ← 流水线核心
scripts/agents/         ← 18 Agent 陪审团
tests/                  ← pytest 测试
configs/                ← YAML 配置文件
voice_packs/            ← 声纹包
genre_packs/            ← 题材模板
style_packs/            ← 风格模板
workspace/              ← 多 DB 工作区（运行时，不提交）
```

## 核心命令
| 命令 | 用途 |
|------|------|
| `python novel.py status` | 环境诊断 |
| `python novel.py demo` | 全流程演示 |
| `python novel.py guards` | 列出门禁 |
| `python novel.py wc 1` | 第1章字数统计 |
| `python novel.py agents review 1 --mode full` | 18 Agent 完整审稿 |
| `python novel.py stability-check --full` | 发布验收 |
| `python novel.py menu` | 交互式菜单 |
| `python novel.py export` | 导出小说 |

## 写作流水线
pre（任务卡）→ 写作 → post（21 guard 门禁）→ review（18 Agent 陪审团）→ ingest（入库）

## 写作规定
- 零引号文学化写法：对话融入叙述，严禁任何引号
- 破折号每千字 ≤5
- 对话占比 ≤10%
- risk_score 越高越差（0=完美, 100=极差）

## 测试
```bash
pytest tests/ -q        # 296 passed
python novel.py stability-check --full  # 发布验收
```

## 配置
- `config.json`：用户配置文件（不提交）
- `config.example.json`：配置模板
- `configs/agents.yaml`：Agent 陪审团配置
