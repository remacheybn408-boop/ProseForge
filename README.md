# Novel Pipeline - Write Engine v0.5.0

[![Test](https://github.com/remacheybn408-boop/novel-pipeline-write-engine/actions/workflows/test.yml/badge.svg?branch=v0.5.0)](https://github.com/remacheybn408-boop/novel-pipeline-write-engine/actions/workflows/test.yml?query=branch%3Av0.5.0)

Novel Pipeline Write Engine 是一个轻量小说工程化写作流水线，专注长篇小说的连续性、角色口吻、AI 腔检查、防幻觉、写前任务卡和写后质量报告。

> **当前版本：v0.5.0 — Stable & Easy Mode。** 统一入口 novel.py、健康检查 status、写前任务卡、Voice/Meme Pack 增强、Reader Pull 追读力门禁、HTML 只读报告。48 个测试文件，268 个测试用例，267 个通过。

---

## 它解决什么问题？

写长篇小说时，AI 很容易出现：

- 每章像真空中写出来，缺少上一章承接
- 人物状态、伤势、任务、伏笔被遗忘
- 新设定突然冒出来，造成幻觉
- 章节越写越像模板，AI 腔、总结腔、说明书腔变重
- 科学设定、修炼体系、剧情因果无法长期保持一致
- 门禁结果不统一：post 报 WARNING，orchestrator 却显示 0 WARNING
- SQLite / FTS5 索引损坏后，后续上下文召回 silently fail

这个项目的目标不是"自动水文"，而是把长篇小说写作拆成可检查、可追踪、可回滚、可审稿的工程流程。

---

## v0.5.0 重点

v0.5.0 是一次稳定易用性升级：

- **统一入口**：`novel.py` 一个命令搞定 init/demo/pre/post/review/status/report
- **健康检查**：`python novel.py status` 一键诊断环境
- **写前任务卡**：自动从 SQLite 提取上下文，生成章节任务卡
- **Voice/Meme Pack 增强**：YAML 模板 + 加载器 + 校验器
- **Reader Pull Guard**：追读力门禁（钩子/兑现/悬念/爽点落地）
- **HTML 只读报告**：纯静态，无需服务器，双击即开
- **5 种题材模板**：修仙/都市/规则怪谈/悬疑/科幻
- **Windows 一键体验**：`install.bat` → `run_demo.bat` → `run_report.bat`

v0.4.5 是一次门禁可信度修复版：

| 模块 | 修复方向 |
|------|----------|
| Guard Registry | post / orchestrator / CI 使用同一套 guard 真相源 |
| WARNING 汇总 | 所有 WARNING 结构化写入 guard_summary.json |
| FTS5 Healthcheck | 检测 invalid fts5 file format，并尝试 rebuild / fallback |
| scene_delta | 从关键词推进改为叙事证据推进 |
| scene_causality | 支持身体代价、环境代价、关系代价、物件后果 |
| continuity | 从词重叠改为承接证据 |
| anti_ai | 统一正则与句式检测入口 |
| path_resolver | 降低 novels_root / slug / 卷目录强耦合 |
| title policy | 标题变化只记录，不擅自改写用户标题 |

---

## 快速开始

### Windows 一键体验

```bat
install.bat
run_demo.bat
run_report.bat          ← 打开 reports/index.html
```

### v0.5.0 统一入口

```bash
python novel.py init     # 初始化项目
python novel.py status   # 健康检查
python novel.py demo     # 跑通 demo
python novel.py pre 1    # 写前任务卡
python novel.py post 1   # 入库 + 门禁
python novel.py review 1 # 写后审稿
python novel.py report   # 生成 HTML 报告
python novel.py export --slug <slug>  # 导出小说合集
```

### 手动运行

```bash
git clone https://github.com/remacheybn408-boop/novel-pipeline-write-engine.git
cd novel-pipeline-write-engine
cp config.example.json config.json

# 初始化数据库
python scripts/init_db.py --config config.json

# 导入 Demo 标题骨架
python scripts/import_outline_skeleton.py --config config.json --input examples/demo_novel/outline_skeleton.json

# 写作前准备
python scripts/chapter_pipeline.py pre 1 --config config.json --novel-slug demo_novel

# 写完 TXT 后入库
python scripts/chapter_pipeline.py post 1 --config config.json --novel-slug demo_novel

# 跑测试
pytest tests/ -v
```

---

## Voice Pack 语言资产系统

v0.4.5 提供通用 Voice Pack / Meme Pack 语言资产系统，用于为不同角色类型提供稳定的说话方式、语体、方言、梗使用边界和禁用词。

**核心是通用的，不绑定任何具体小说角色。**

### 特点

- **不绑定角色**：所有 base pack 使用通用角色类型（如 `protagonist_science_monk`），不写死具体角色名
- **YAML 管理**：纯 YAML 配置文件，零依赖，可被脚本/Agent/任何工具解析
- **通用类型**：8 种通用角色类型 + 8 种语体 + 5 种方言 + 7 种梗包
- **禁用梗库**：内置 `forbidden_memes.yaml`，默认禁止高频网络热梗（家人们谁懂啊/尊嘟假嘟/yyds 等）
- **不依赖 GUI/LLM**：纯配置驱动，不绑定特定前端或模型

## Guard Calibration Loop（校准型混合门禁）

v0.4.5 引入门禁校准循环，在规则门禁之上增加特征提取、风险路由和样本评估，让门禁从"凭感觉调参"升级为"可评估、可校准"。

- **Feature Extractor**：15 项结构化特征（抽象词密度、动作密度、梗密度等）
- **Risk Router**：6 条路由规则，自动降级误判、升级高风险
- **Golden Corpus**：40 个标注样本，可量化 precision/recall
- **Shadow Mode**：新门禁先影子运行，不影响原有结果
- **默认不依赖 LLM**：Semantic Judge 预留但 mode=off

详见 `docs/guard_calibration_loop.md`

### 目录结构

```
voice_packs/
├── base/          ← 通用角色声纹包（9个）
├── registers/     ← 语体包（8个）
├── dialects/      ← 方言包（5个）
├── memes/         ← 梗语言包（7个）
├── bindings/      ← 角色绑定模板
└── samples/       ← 好坏示例
```

核心系统提供通用角色类型绑定模板（`voice_packs/bindings/demo_bindings.yaml`），支持 8 种通用角色类型：

- 理工型主角 · 接地气好兄弟 · 武力型对手 · 工匠型长者
- 冷契约型反派 · 半文言老祖 · 市井商人 · 动作化旁白

具体小说角色绑定属于 examples，应放在 `examples/novels/<novel_slug>/character_bindings.yaml`，不在 engine core 中。详见 `voice_packs/bindings/demo_bindings.yaml` 和以下文档：

- [Voice Pack 通用资产说明](docs/voice_pack_assets.md)
- [Meme Pack 梗语言资产](docs/meme_pack_assets.md)
- [Dialect Pack 方言资产](docs/dialect_pack_assets.md)
- [角色绑定指南](docs/voice_pack_binding_guide.md)

---

## 目录结构

```
novel-pipeline-write-engine/
├── config.example.json              ← 配置模板
├── config.json                      ← 你的本地配置（gitignore）
├── install.bat / run_demo.bat       ← Windows 一键安装/运行
├── run_report.bat                   ← 双击打开 HTML 报告
├── novel.py                         ← [v0.5.0] 统一入口
├── templates/                       ← [v0.5.0] 题材/声纹/梗模板
│   ├── genres/                      ← 5 种题材模板
│   ├── voice_pack/                  ← 声纹 YAML 模板
│   └── meme_pack/                   ← 梗包 YAML 模板
├── src/                             ← [v0.5.0] 模块化源码
│   ├── cli/                         ← CLI 命令
│   ├── guards/                      ← Reader Pull / Voice / Meme Guard
│   ├── task_card/                   ← 写前任务卡
│   ├── voice/                       ← Voice Pack 加载器
│   ├── meme/                        ← Meme Pack 加载器
│   └── report/                      ← HTML 报告生成
├── scripts/
│   ├── chapter_pipeline.py          ← 主流水线（pre / post / review / volume）
│   ├── guard_registry.py            ← [v0.4.5] 统一门禁注册入口
│   ├── guard_result.py              ← [v0.4.5] GuardResult / GuardSummary 数据结构
│   ├── anti_ai_patterns.py          ← [v0.4.5] AI腔统一规则库
│   ├── consequence_lexicon.py       ← [v0.4.5] 可见后果词库
│   ├── fts_health.py                ← [v0.4.5] FTS5 自愈
│   ├── bridge_evidence_guard.py     ← [v0.4.5] 章间承接证据
│   ├── path_resolver.py             ← [v0.4.5] 灵活目录模板
│   ├── guard_orchestrator.py        ← 门禁总控调度
│   ├── init_db.py / check_schema.py ← 数据库初始化
│   └── ... (20+ guards)
│
├── database/
│   └── schema.sql                   ← SQLite schema（26 表 + 6 FTS5）
│
├── examples/
│   ├── demo_novel/                  ← Demo 骨架
│   ├── demo_chapters/               ← Demo 章节样本
│   └── demo_reports/                ← Demo 报告样本
│
├── tests/                           ← 48 个测试文件，295 个测试用例
├── docs/                            ← 架构 / 规范 / 发布说明
│   ├── releases/                    ← 历史版本发布说明
│   └── skills/                      ← Agent 写作路由
│
├── .github/workflows/test.yml       ← CI（pytest 自动跑）
└── README.md
```

---

## 核心能力

| 能力 | 作用 |
|------|------|
| SQLite 长期记忆 | 记录章节、人物、设定、摘要、标题、状态 |
| Chapter Pipeline | pre / post / review / volume 分阶段处理 |
| Guard Registry | 统一所有门禁入口，避免多入口结果漂移 |
| Continuity Evidence | 检查上一章状态、钩子、任务是否被承接 |
| Hallucination Guard | 阻止无依据新设定、矛盾设定、遗忘状态 |
| Scene Delta Guard | 检查场景是否真的发生推进 |
| Scene Causality Guard | 检查行动是否带来可见后果 |
| Anti-AI / QGP | 检测模板化、重复、总结腔、异常平滑 |
| Revision Loop | 输出可审阅的改稿建议，默认不覆盖原文 |
| Backup DB | 写作前备份 SQLite，降低数据损坏风险 |

---

## 工作流

```text
outline skeleton
    ↓
chapter_pipeline pre        ← 读上章结尾 + 查 SQLite + 出 task card
    ↓
write chapter txt           ← 正文写作（必须走 novel-factory skill）
    ↓
chapter_pipeline post       ← 跑全部门禁
    ↓
guard registry              ← 统一门禁入口 → guard_summary.json
    ↓
ingest to SQLite            ← 入库 + 切片 + FTS + 版本 + 摘要
    ↓
next chapter context        ← 自动读取上章 brief，进入下章 pre
```

---

## 适合谁使用？

- 想写 50 万字以上长篇小说的人
- 想让 AI 写作有长期记忆的人
- 想降低 AI 腔、模板腔、说明书腔的人
- 想做玄幻、科幻、修仙、连续剧情工程化写作的人
- 想让 Agent 按流程写，而不是普通聊天随便续写的人

---

## 文档导航

- [v0.5.0 Stable & Easy Mode 详解](docs/V050_STABLE_EASY_MODE.md) ← 必读
- [架构说明](docs/architecture.md)
- [数据库 Schema](docs/database.md)
- [流水线说明](docs/pipeline.md)
- [路线图](docs/ROADMAP.md)
- [更新日志](CHANGELOG.md)
- [Guard Registry](docs/GUARD_REGISTRY.md)
- [FTS5 自愈](docs/README_FULL.md#fts5)
- [Hermes Agent 写作规则](docs/HERMES_AGENT_RULES.md)
- [角色口吻与动作证据系统](docs/character_voice_action_proof_system.md)
- [QGP 困惑度质量门禁](docs/PERPLEXITY_QGP.md)
- [拟人审稿质量套件](docs/HUMAN_GRADE_REVISION_SUITE.md)
- [改稿闭环](docs/REVISION_LOOP.md)
- [部署指南](docs/setup-guide.md)
- [Voice Pack 通用资产](docs/voice_pack_assets.md)
- [Meme Pack 梗语言资产](docs/meme_pack_assets.md)
- [Dialect Pack 方言资产](docs/dialect_pack_assets.md)
- [角色绑定指南](docs/voice_pack_binding_guide.md)

### Agent Skill 文档

- [novel-factory Router](docs/skills/novel_factory_router_SKILL.md) — 正文写作前必读
- [长篇写作行为规范](docs/skills/long_novel_writing_SKILL.md)

---

## 特性一览

| 维度 | Novel Pipeline WE |
|------|-------------------|
| 定位 | 轻量小说质量流水线 |
| 入口 | `novel.py` 一条命令搞定全部流程 |
| 许可证 | MIT OR GPL-3.0 双许可 |
| 依赖 | Python + SQLite，无需 Docker / Node / npm |
| 报告 | 纯 HTML，双击即开，无 CDN |
| 门禁 | 17+ 规则门禁，可校准 |
| Voice Pack | 41 个 JSON + YAML 声纹包，方言/语体/梗/英语全覆盖 |
| 学习曲线 | 5 分钟跑通 demo |
| 适用 | 个人作者、小团队 |

本项目的核心哲学：**能简单就不要复杂，能稳定就不要炫技。**

---

## Roadmap

| 版本 | 计划 |
|------|------|
| v0.5.0 | Stable & Easy Mode（当前版本） |
| v0.5.1 | 多 Agent 实验性支持 |
| v0.6.0 | Voice Pack 自动扩写 + 改稿推荐 |
| v0.7.0 | 多小说宇宙联动 + 跨卷伏笔 |
| v1.0.0 | 完整 GUI + 发布 |

详见 [docs/ROADMAP.md](docs/ROADMAP.md)

---

## 版本历史

| 版本 | 重点 |
|------|------|
| v0.5.0 | Stable & Easy Mode — 统一入口 + 健康检查 + 写前任务卡 + Reader Pull Guard + HTML 报告 |
| v0.4.5 | Guard Truth Source Fix — 门禁可信度修复 |
| v0.4.0 | Human-Grade Revision Suite — 拟人审稿 + 改稿闭环 |
| v0.3.1 | Quality Guard Patch — 误判校准 + 角色口吻 + QGP |

详见 [docs/releases/](docs/releases/)

---

## License

本项目采用双许可：**MIT OR GPL-3.0**（用户可任选其一）。

- **MIT**：最宽松，允许闭源商用，只需保留版权声明
- **GPL-3.0**：强制开源，修改和分发必须保持同协议

详情见 [LICENSE](LICENSE)。
