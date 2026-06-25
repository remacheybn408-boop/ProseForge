# ProseForge — 普通用户操作手册 v0.8.0

> 适用版本：v0.8.0 及以上

---

## 工具总览（重要）

ProseForge **没有 Web/浏览器界面**，也没有一堆中文命名的工具。所有功能只通过 **2 个工具**提供，
每个工具用 `action` 参数选择具体操作：

| 工具 | action | 作用 |
|------|--------|------|
| `nf_project` | `init` / `create` / `list` / `status` / `outline` / `export` | 项目/工作区/大纲管理 |
| `nf_pipeline` | `pre` / `post` / `review` / `batch` / `volume` / `rewrite` / `accept` | 写作流水线 |

三个使用面共享同一内核：
- **Hermes**：在 Hermes Agent 里直接调 `nf_project(...)` / `nf_pipeline(...)` 工具
- **Codex / Claude**：跑命令 `python plugin/proseforge-codex/scripts/nf_pipeline.py --action ...`
  （Claude 面的 skill 也是转调这套 codex 脚本）

下文示例以 Hermes 工具调用写法为主；括号里给出等价 action。

---

## 目录

1. [这个工具是干什么的](#1-这个工具是干什么的)
2. [安装](#2-安装windows--macos--linux)
3. [第一次启动（初始化）](#3-第一次启动初始化)
4. [创建第一部小说](#4-创建第一部小说)
5. [添加大纲](#5-添加大纲)
6. [为什么没有大纲就不能写](#6-为什么没有大纲就不能写)
7. [写第一章（pre → 写文 → post → 报告）](#7-写第一章pre--写文--post--报告)
8. [审稿（review agents）](#8-审稿review-agents)
9. [改写闭环（rewrite / accept）](#9-改写闭环rewrite--accept)
10. [管理工作区和大纲](#10-管理工作区和大纲)
11. [常用调用速查](#11-常用调用速查)

---

## 1. 这个工具是干什么的

ProseForge 是一个帮你**工程化写长篇小说**的系统（命令行 / Agent 工具，无 GUI）。

它不帮你"自动水文"——它帮你：

- **记住前面写了什么**：角色状态、伏笔、设定，不会写着写着忘了。
- **写前告诉你该写什么**：自动生成"任务卡"，告诉你这章需要承接什么、推进什么、禁止写什么。
- **写后帮你检查质量**：registry 派发 10 个门禁（另有 human_texture 平行路径 11 个），把 AI 腔、幻觉设定、情节断裂、缺少后果等揪出来。
- **多角度审稿**：6 个审读 Agent + Chief Editor 聚合层，从对话、场景、人物、追读力等维度出报告（纯规则，不调 LLM）。
- **版本管理**：章节版本快照永不覆盖，大纲可切换。

它是一个"写作+检查+记忆"系统，不是"输入一句话自动出正文"的工具。

---

## 2. 安装（Windows / macOS / Linux）

### 前提条件
- **Python 3.10 或更高版本**
- **Git**（可选）

### Windows
```powershell
git clone https://github.com/remacheybn408-boop/ProseForge.git
cd ProseForge
python -m venv .venv
.venv\Scripts\activate
pip install -e .            # RAG 可选：pip install -e .[rag]
copy config.example.json config.json
```

### macOS / Linux
```bash
git clone https://github.com/remacheybn408-boop/ProseForge.git
cd ProseForge
chmod +x install.sh
./install.sh
```

---

## 3. 第一次启动（初始化）

初始化工作区：

1. **`nf_project(action="init")`** — 创建 workspace 目录和数据库
2. **`nf_project(action="status")`** — 确认环境正常

这会创建：
- `workspace/registry.json`：工作区注册表（**初始为空，不预创建任何 slot**）
- `workspace/<slug>/`：第一次 `nf_project(action="outline", sub_action="add", ...)` 时根据大纲 title 自动派生 slug 创建

---

## 4. 创建第一部小说

引擎用 **DB 工作区（slot）** 隔离不同小说的数据和文件：

1. **`nf_project(action="list")`** — 查看已有工作区
2. **`nf_project(action="create", slot_name="slot_004", title="我的第一本修仙小说")`** — 创建新小说

> 创建新工作区会自动生成 slot_004、slot_005……

---

## 5. 添加大纲

### 为什么需要大纲？
**没有大纲就不能开始写**。引擎需要大纲来生成写前任务卡、检查偏离、做相似度检测。

### 创建大纲文件
先建一个 `.txt`，格式自由，建议包含标题/题材/主角/世界观/分卷分章要点，例如：

```
# 标题：青云问道
## 题材：修仙 / 玄幻
## 主角：李明远（外门弟子，身怀神秘玉佩）
## 第一卷：初入宗门
- 第1章：外门晨练，玉佩异动，大长老临时复测根骨
- ...
```

### 添加大纲
1. **`nf_project(action="outline", sub_action="add", file_path="大纲.txt")`**
2. **`nf_project(action="outline", sub_action="list", slot_name="slot_004")`**

> 添加大纲时会**自动相似度检测**：若工作区已有大纲，引擎会对比并给建议。

---

## 6. 为什么没有大纲就不能写

设计哲学：**没有计划的写作是堆字数，不是创作**。没有激活大纲时跑 `pre`/`post` 会被拦下，
提示先 `nf_project(action="outline", sub_action="add", ...)`。这不是 bug，是设计。

---

## 7. 写第一章（pre → 写文 → post → 报告）

v0.8.0 标准流程：

```
大纲 → pre（任务卡） → 写正文 → post（门禁+入库） → 报告
```

### 步骤 1：pre —— 生成写前任务卡
```
nf_pipeline(action="pre", slug="<slug>", title="<小说名>", vol_no=1, chapter_no=1)
```
从 DB 提取上章（第一章则从大纲）上下文，生成任务卡：承接什么 / 推进什么 / 禁止写什么。

### 步骤 2：写正文
按任务卡写出 `.txt`，放到对应位置：
```
workspace/<slot>/chapters/第01卷/第1章_开篇.txt
```
（不确定 slug 就 `nf_project(action="status")` 查看激活槽位。）

### 步骤 3：post —— 跑门禁 + 入库
```
nf_pipeline(action="post", slug="<slug>", title="<小说名>", vol_no=1, chapter_no=1)
```
这会：字数门禁 → 10 个 registry 门禁（连续性 / 反 AI 腔 / 场景推进 / 追读力 / 合规…）
→ human_texture 检查 → 去重修改任务 → **入库（追加 chapter_versions 快照）** + stage_review。
严重问题会报 WARNING 或 FAIL。

### 步骤 4：查看报告
- 门禁报告在 `exports/reports/chapter_NNN_*.json`
- 卷级总结：**`nf_pipeline(action="volume", slug="<slug>", title="<小说名>", vol_no=1)`**

---

## 8. 审稿（review agents）

写完一章后让 AI 审读团审稿：

```
nf_pipeline(action="review", slug="<slug>", vol_no=1, chapter_no=1, mode="full")
```

- `mode="light"`：跑 3 个 Agent（continuity / prose / plot）
- `mode="full"`：跑 6 个 Agent（再加 character / reader / detail）

6 个审读 Agent 关注：对话与潜台词、场景落地与动作、情节推进与伏笔、连续性与设定、
人物心理、情绪曲线与追读力、反 AI 腔。**纯规则，不调 LLM。**
Chief Editor 汇总去重并分类 `must_fix / should_fix / keep`。**审稿不覆盖正文，只出报告。**

批量跑多章 post：`nf_pipeline(action="batch", slug=..., title=..., vol_no=1, from_ch=1, to_ch=5)`。

---

## 9. 改写闭环（rewrite / accept）

按门禁/审稿发现的问题做**受约束的改稿**（详见 [REVISION_LOOP.md](REVISION_LOOP.md)）：

1. **`nf_pipeline(action="rewrite", slug=..., title=..., vol_no=1, chapter_no=1)`**
   —— 读 post 的去重报告，生成「改写卡」到 `outputs/rewrite_cards/`
2. 按改写卡只改问题段，把全章写入 `chapter_NNN_revised.txt`
3. **`nf_pipeline(action="accept", ..., chapter_no=1, ingest=true)`**
   —— 原稿 vs 改稿出 diff + 风险标记；审核通过则入库（追加快照，**不覆盖原稿**）

内核不调 LLM：正文改写由你 / Agent 执行，内核只给约束与验收。

---

## 10. 管理工作区和大纲

| 操作 | 调用 |
|------|------|
| 列出工作区 | `nf_project(action="list")` |
| 创建工作区 | `nf_project(action="create", slot_name="...", title="...")` |
| 查看激活槽位 | `nf_project(action="status")` |
| 添加大纲 | `nf_project(action="outline", sub_action="add", file_path="大纲.txt")` |
| 列出大纲 | `nf_project(action="outline", sub_action="list", slot_name="...")` |
| 切换大纲 | `nf_project(action="outline", sub_action="switch", slot_name="...")` |
| 导出小说 | `nf_project(action="export", slug="...", format="txt")` |

> 大纲对比（compare）和回滚（rollback）逻辑在 `src/outline/`，目前未封装为独立 action，可先 list 后手动操作。

相似度检测维度（添加大纲时自动）：标题(15%) / 角色重叠(25%) / 世界观关键词(25%) /
章节结构(15%) / 题材风格(20%)。≥70 建议升级、35–69 不确定、<35 建议新建工作区。

---

## 11. 常用调用速查

| 目的 | Hermes 调用 | 等价 action |
|------|-------------|-------------|
| 初始化 | `nf_project(action="init")` | nf_project init |
| 状态诊断 | `nf_project(action="status")` | nf_project status |
| 创建小说 | `nf_project(action="create", slot_name=, title=)` | nf_project create |
| 列出工作区 | `nf_project(action="list")` | nf_project list |
| 大纲管理 | `nf_project(action="outline", sub_action=add/list/switch)` | nf_project outline |
| 导出 | `nf_project(action="export", slug=, format=)` | nf_project export |
| 写前任务卡 | `nf_pipeline(action="pre", ...)` | nf_pipeline pre |
| 写后门禁+入库 | `nf_pipeline(action="post", ...)` | nf_pipeline post |
| 审稿 | `nf_pipeline(action="review", ..., mode=)` | nf_pipeline review |
| 批量 post | `nf_pipeline(action="batch", ..., from_ch=, to_ch=)` | nf_pipeline batch |
| 卷总结 | `nf_pipeline(action="volume", ...)` | nf_pipeline volume |
| 改写产卡 | `nf_pipeline(action="rewrite", ...)` | nf_pipeline rewrite |
| 改稿对比/入库 | `nf_pipeline(action="accept", ..., ingest=)` | nf_pipeline accept |

---

## 遇到问题？

- 先 `nf_project(action="status")` 确认环境正常
- 确认 `config.json` 存在且配置正确
- 确认大纲已添加且激活（`nf_project(action="outline", sub_action="list")`）
- 查看 [README.md](../README.md) 和 [CHANGELOG.md](../CHANGELOG.md)
