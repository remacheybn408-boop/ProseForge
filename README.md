# ProseForge

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
![Version](https://img.shields.io/badge/version-v0.9.0-orange)
![Surfaces](https://img.shields.io/badge/surfaces-Hermes%20%7C%20Codex%20%7C%20Claude-brightgreen)
![License](https://img.shields.io/badge/license-see%20LICENSE-lightgrey)

`ProseForge` 是一个面向长篇小说的工程化写作系统。  
它不只是“生成一章文本”的提示词仓库，而是一套从大纲、写前准备、写后门禁、审读、改写到导出的完整工作流。

一句话理解：

> 它要解决的不是“怎么多写一点”，而是“怎么把一本书持续写下去，而且尽量不写崩”。

---

## 这个项目解决什么问题

长篇小说一旦进入几十章以后，最常见的问题不是没灵感，而是失控：

- 角色口吻前后不一致
- 世界观和设定互相打架
- 上一章埋的东西，下一章接不上
- 写前没有任务卡，写后没有质量门禁
- 改稿只能靠人工来回翻，缺少闭环
- 不同 Agent / 不同插件表面，调用方式不统一

`ProseForge` 的目标，就是把这些问题收束到一套统一流程里。

---

## 一眼看懂这套系统

### 用户视角

如果你是使用者，可以把它理解成这条主链：

```text
大纲
  -> nf_project outline add
  -> nf_pipeline pre
  -> 正式写章节
  -> nf_pipeline post
  -> nf_pipeline review
  -> nf_pipeline volume
  -> nf_project export
```

最核心的闭环是：

```text
pre -> write -> post
```

也就是：

1. 先做写前准备
2. 再写正文
3. 写完后跑质量门禁和入库

`review` 是质量增强层，`volume` 和 `export` 是阶段收尾层。

### 架构视角

如果你是第一次看仓库，建议把它理解成“一个共享内核，两个主入口，三个插件表面”：

```text
Hermes / Codex / Claude
    -> nf_project / nf_pipeline
    -> 本地 wrapper / plugin surface
    -> src/bios.py
    -> src/pipeline/
        -> pre / post / volume / export
        -> guards
        -> review agents
        -> revision planner
    -> workspace/<slot>/
        -> novel.db
        -> outlines/
        -> chapters/
        -> reports/
        -> exports/
```

这也是整个仓库最重要的设计原则：

- 对外入口尽量少
- 内核逻辑尽量共享
- 不同平台尽量使用同一种心智模型

---

## 系统架构

### 1. 入口层

对外只有两个主入口：

| 入口 | 作用 | 典型动作 |
| --- | --- | --- |
| `nf_project` | 管项目和工作区 | `init` / `create` / `list` / `status` / `outline` / `export` |
| `nf_pipeline` | 管章节流水线 | `pre` / `post` / `review` / `batch` / `volume` |

它们是用户最应该记住的两个名字。

### 2. 共享内核层

真正的业务逻辑主要在 `src/` 下面：

| 目录 | 作用 |
| --- | --- |
| `src/pipeline/` | 写前、写后、卷汇总、导出、任务卡、报告等主流水线 |
| `src/guards/` | 质量门禁系统和统一注册入口 |
| `src/agents/` | 多 Agent 审读系统 |
| `src/db/` | workspace、slot、registry、数据库管理 |
| `src/outline/` | 大纲导入、切换、版本相关逻辑 |
| `src/story/` | story contract、章节承接、story health |
| `src/revision_planner/` | 新版改写规划与执行路径 |
| `src/voice/` | voice pack 和角色口吻相关支持 |

`src/bios.py` 是一个很薄的统一分派层，用来把外部动作接到内部 pipeline。

### 3. 质量门禁层

`post` 之后最关键的一层就是 Guard 系统。

它负责检查：

- 连续性
- 设定证据一致性
- 幻觉和捏造
- 场景推进
- 对话质量
- 读者卷入度
- 文本真实感
- 自检与合规

你可以把它理解成“章节写完以后的一道总闸门”。

### 4. 审读层

`review` 走的是 `src/agents/` 里的多 Agent 审读系统。

当前有两种模式：

- `light`：轻量审读
- `full`：完整审读

入口在：

- `src/agents/orchestrator.py`

这层更像“编辑部复盘”，不是单纯的规则检查。

### 5. 改写层

当前仓库里同时存在两条改写路线：

- `src/rewriter.py`：遗留改写实现，已不再作为 `nf_pipeline` 对外动作
- `src/revision_planner/`：新版 revision planning 路径

历史上的 `rewrite` 路径有一个重要特点：

- 输出 `.revised.txt`
- 不覆盖原始章节文件

这点很重要，因为它保证改稿是增量产物，而不是直接破坏原稿。

### 6. 存储层

工作区使用 `workspace/` 作为项目容器，每个 `slot` 都可以看成一部小说的独立工作区。

典型结构如下：

```text
workspace/
|- registry.json
|- slot_001/
|  |- novel.db
|  |- project.json
|  |- outlines/
|  |- chapters/
|  |- reports/
|  |- exports/
|  `- backups/
|- slot_002/
`- slot_003/
```

这里最值得记住的一点是：

> 一个 `slot` 基本就等于一个独立项目容器。不同小说尽量不串库、不串上下文、不串报告。

---

## 两个主入口怎么用

### `nf_project`

`nf_project` 负责项目和工作区管理。

| action | 作用 |
| --- | --- |
| `init` | 初始化本地 `workspace/`、registry 和默认 slot |
| `create` | 新建一个 slot / 项目容器 |
| `list` | 列出已注册 slot |
| `status` | 查看当前活动 slot 和 registry 状态 |
| `outline` | 添加 / 列出 / 切换大纲 |
| `export` | 导出小说，支持 `txt` / `md` |

可以把它理解成“工程台”和“资料台”。

### `nf_pipeline`

`nf_pipeline` 负责写作流水线本身。

| action | 作用 |
| --- | --- |
| `pre` | 写前准备，生成任务卡、上下文和流水线状态 |
| `post` | 写后处理，跑门禁、报告、入库等 |
| `review` | 多 Agent 审读 |
| `batch` | 批量跑章节 `post` |
| `volume` | 生成卷级汇总和桥接信息 |

可以把它理解成“章节生产线”。

---

## 推荐的标准使用顺序

### 第一次开新项目

```bash
python plugin/proseforge-codex/scripts/nf_project.py --action init
python plugin/proseforge-codex/scripts/nf_project.py --action status
python plugin/proseforge-codex/scripts/nf_project.py --action outline --sub-action add --file-path examples/demo_novel/outline_skeleton.json
python plugin/proseforge-codex/scripts/nf_pipeline.py --action pre --slug demo_novel --title "Demo Novel" --vol-no 1 --chapter-no 1
```

然后你去写正文，写完再继续：

```bash
python plugin/proseforge-codex/scripts/nf_pipeline.py --action post --slug demo_novel --title "Demo Novel" --vol-no 1 --chapter-no 1
python plugin/proseforge-codex/scripts/nf_pipeline.py --action review --slug demo_novel --vol-no 1 --chapter-no 1 --mode full
python plugin/proseforge-codex/scripts/nf_pipeline.py --action volume --slug demo_novel --title "Demo Novel" --vol-no 1
```

### 日常章节写作

日常最常用的是这条链：

```text
status -> pre -> write -> post
```

也就是：

1. 先确认当前活动 slot
2. 做 `pre`
3. 写正文
4. 跑 `post`

如果章节有问题，再接：

```text
review
```

---

## 几条很重要的工作规则

- 所有 wrapper script 最好都在仓库根目录执行
- 在跑 slot-aware 的流程之前，先 `init` 一次 workspace
- 在 `pre` 之前先导入 outline，这套系统本质上是 outline-driven
- `slug`、`title`、`vol-no`、`chapter-no` 在整条章节生命周期里要尽量一致
- `review --mode light` 适合快速检查，`review --mode full` 适合完整复盘
- 旧版 `rewrite` 动作已下线；需要修订时请用 `review` 结果驱动人工或后续 planner 流程

如果你只记一条规则，请记这条：

> 先有大纲，再做 `pre`；先做 `pre`，再写正文；写完正文，再跑 `post`。

---

## 插件表面

当前仓库里可以看到三种表面：

| 表面 | 位置 | 特点 |
| --- | --- | --- |
| Hermes | `plugin/proseforge-Hermes/` | 面向 Hermes 的插件入口 |
| Codex | `plugin/proseforge-codex/` | 面向 Codex 的本地插件骨架和共享 wrapper |
| Claude | `plugin/proseforge-claude/` | 面向 Claude Code 的 skill 包装 |

虽然外层平台不同，但内部尽量共用同一套入口名和同一套逻辑。

这也是为什么 README 一直强调：

- `nf_project`
- `nf_pipeline`

因为这两个名字才是跨平台稳定的“公共语言”。

---

## 代码导览

如果你要快速读代码，推荐顺序如下：

1. `plugin/proseforge-codex/scripts/nf_project.py`
2. `plugin/proseforge-codex/scripts/nf_pipeline.py`
3. `src/bios.py`
4. `src/pipeline/pre.py`
5. `src/pipeline/post.py`
6. `src/agents/orchestrator.py`
7. `src/guards/guard_registry.py`

原因很简单：

- 先看 wrapper，知道外部怎么进来
- 再看 `bios.py`，知道动作怎么分派
- 再看 `pre` / `post`，知道主流水线怎么跑
- 再看 `agents` 和 `guards`，知道质量系统怎么挂上去

---

## 仓库目录速览

```text
ProseForge/
|- src/                      # 共享 Python 内核
|- plugin/                   # Hermes / Codex / Claude 三类表面
|- configs/                  # 配置
|- packs/                    # genre / style / template / voice 资源
|- workspace/                # 本地工作区与 slot
|- docs/                     # 架构、指南、说明文档
|- examples/                 # demo outline / demo chapter / demo reports
|- exports/                  # 导出和流水线产物
`- tests/                    # 测试
```

如果你是使用者，重点看：

- `plugin/`
- `workspace/`
- `examples/`
- `docs/`

如果你是开发者，重点看：

- `src/pipeline/`
- `src/guards/`
- `src/agents/`
- `src/db/`

---

## 快速开始

下面的命令默认都在仓库根目录执行：

```bash
git clone https://github.com/bijinfeng/novel-pipeline-write-engine.git
cd novel-pipeline-write-engine
python -m pip install -e .
python -m pip install pytest
python -m pytest
```

如果你需要可选的 retrieval 依赖：

```bash
python -m pip install -e ".[rag]"
```

如果你准备长期本地使用，建议复制：

```text
config.example.json -> config.json
```

再按自己的路径做配置。

---

## 相关文档

如果 README 还不够，可以继续看这些文件：

- `docs/architecture.md`：系统架构说明
- `docs/setup-guide.md`：安装和环境说明
- `docs/USER_GUIDE_CN.md`：更完整的中文用户手册
- `docs/README_FULL.md`：旧版长说明
- `examples/demo_novel/outline_skeleton.json`：可直接导入的 demo 大纲
- `examples/demo_novel/README.md`：示例项目说明

---

## 当前状态

- Core version: `v0.9.0`
- Python requirement: `>=3.10`
- Optional extra: `rag`
- Repository: `https://github.com/bijinfeng/novel-pipeline-write-engine`
- License: see `LICENSE`

当前这个仓库的方向，可以概括成一句话：

> 一个共享内核，两个主入口，三个插件表面，一条面向长篇小说的工程化流水线。

---

## 赞助

如果你觉得这个项目有帮助，欢迎用支付宝支持作者：

![支付宝收款码](assets/alipay.jpg)
