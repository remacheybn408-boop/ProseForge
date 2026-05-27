# Novel Pipeline Write Engine — 普通用户操作手册 v0.6.5

> 最后更新：2026-05-26
> 适用版本：v0.6.5 及以上

---

## 目录

1. [这个工具是干什么的](#1-这个工具是干什么的)
2. [安装（Windows / macOS / Linux）](#2-安装windows--macos--linux)
3. [第一次启动（初始化）](#3-第一次启动初始化)
4. [创建第一部小说](#4-创建第一部小说)
5. [添加大纲](#5-添加大纲)
6. [为什么没有大纲就不能写](#6-为什么没有大纲就不能写)
7. [写第一章（pre → 写文 → post → report）](#7-写第一章pre--写文--post--report)
8. [审稿（jury / agents）](#8-审稿jury--agents)
9. [管理 DB 工作区和大纲](#9-管理-db-工作区和大纲)
10. [大纲的相似度检测](#10-大纲的相似度检测)
11. [常用命令速查](#11-常用命令速查)

---

## 1. 这个工具是干什么的

Novel Pipeline Write Engine 是一个帮你**工程化写长篇小说**的命令行工具。

它不帮你"自动水文"——它帮你：

- **记住前面写了什么**：角色状态、伏笔、设定，不会写着写着忘了。
- **写前告诉你该写什么**：自动生成"任务卡"，告诉你这章需要承接什么、推进什么、禁止写什么。
- **写后帮你检查质量**：21 个门禁检查，AI 腔、幻觉设定、情节断裂、缺少后果……全给你揪出来。
- **多角度审稿**：8 个专业 Agent 并行审稿，从对话、场景、人物、追读力等维度打分。
- **版本管理**：大纲可以回滚，章节可以备份，不用担心改坏。

它是一个"写作+检查+记忆"系统，不是一个"输入一句话自动出正文"的工具。

---

## 2. 安装（Windows / macOS / Linux）

### 前提条件

- **Python 3.10 或更高版本**
- **Git**（可选，用于克隆代码）

### Windows

```bat
:: 1. 克隆仓库
git clone https://github.com/remacheybn408-boop/novel-pipeline-write-engine.git
cd novel-pipeline-write-engine

:: 2. 双击运行安装脚本
install.bat

:: 3. 体验 demo
run_demo.bat

:: 4. 查看报告
run_report.bat
```

**手动安装（如果不使用脚本）：**

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json
```

### macOS

```bash
git clone https://github.com/remacheybn408-boop/novel-pipeline-write-engine.git
cd novel-pipeline-write-engine

chmod +x install.sh
./install.sh
```

### Linux

```bash
# Ubuntu/Debian 先装 Python
sudo apt install python3 python3-venv python3-pip

git clone https://github.com/remacheybn408-boop/novel-pipeline-write-engine.git
cd novel-pipeline-write-engine

chmod +x install.sh
./install.sh
```

---

## 3. 第一次启动（初始化）

安装完成后，运行：

```bash
python novel.py init
```

这会创建：
- `config.json`：项目配置文件
- `data/novel_memory.db`：SQLite 长期记忆数据库
- `workspace/`：工作区目录（大纲、章节、报告）
- 必要的输出和临时目录

运行健康检查确认一切正常：

```bash
python novel.py status
```

输出示例：

```
============================================================
  Novel Pipeline - Write Engine 0.6.5
  状态检查 (标准)
============================================================

  [OK] OS: Windows 10 ...
  [OK] Python 3.11
  [OK] config.json
  [OK] src/guards/reader_pull_guard.py
  ...

  All checks passed. Ready to write.
```

---

## 4. 创建第一部小说

引擎使用 **DB 工作区（slot）** 来隔离不同小说的数据和文件。默认有 3 个空工作区。

```bash
# 查看当前工作区
python novel.py db list

# 创建新小说的工作区
python novel.py db new --name "我的第一本修仙小说"

# 切换到它
python novel.py db use slot_004
```

> 创建新工作区时会自动生成 slot_004、slot_005……以此类推。

---

## 5. 添加大纲

### 为什么需要大纲？

**没有大纲就不能开始写**。引擎需要大纲来：
- 生成写前任务卡时知道"这章要写什么"
- 检查章节是否偏离大纲设定
- 进行相似度检测（防止把修真大纲写到都市小说里）

### 创建大纲文件

先创建一个 `.txt` 文件，格式自由，建议包含：

```
# 标题：青云问道

## 题材：修仙 / 玄幻

## 主角：李明远（外门弟子，身怀神秘玉佩）

## 世界观：
- 青云宗：七大仙门之一，分内门外门
- 修炼境界：炼气 → 筑基 → 金丹 → 元婴
- 测灵石：能检测弟子根骨

## 第一卷：初入宗门
- 第1章：外门晨练，玉佩异动，大长老临时复测根骨
- 第2章：根骨测试暴露青金色灵根，被戒律堂盯上
- 第3章：深夜后山禁地，发现玉佩与封印阵的关联
- ...
```

### 添加大纲

```bash
# 方式1：直接添加
python novel.py outline add 大纲.txt

# 方式2：导入（指定标题、题材、风格）
python novel.py outline import 大纲.txt --title "青云问道" --genre 修仙 --style 热血

# 查看已添加的大纲
python novel.py outline list

# 查看当前激活的大纲
python novel.py outline current
```

> 添加大纲时会**自动进行相似度检测**，如果当前工作区已有大纲，引擎会对比两者并给出建议（见第10章）。

---

## 6. 为什么没有大纲就不能写

引擎的设计哲学是：**没有计划的写作是堆字数，不是创作**。

如果你在没有大纲的情况下运行 `pre`、`post` 或 `story contract`，会看到：

```
============================================================
  ⛔ 没有激活的大纲
============================================================

  当前小说没有激活大纲，不能开写。
  请先执行: python novel.py outline add 大纲.txt

  或者导入已有大纲:
  python novel.py outline import 大纲.txt --title "我的小说"
```

这不是 bug，是设计。请先规划好故事骨架再动笔。

---

## 7. 写第一章（pre → 写文 → post → report）

v0.6.5 的标准写作流程：

```
大纲 → pre（任务卡） → 写正文 → post（门禁+入库） → report（查看报告）
```

### 步骤 1：pre —— 生成写前任务卡

```bash
python novel.py pre 1
```

这会从数据库提取上一章（如果是第一章则从大纲提取）的上下文，生成一张"任务卡"：

- **承接了什么**：上一章结尾的悬念、未解决的伏笔
- **本章推进什么**：大纲中第1章的剧情要点
- **禁止写什么**：不能新引入的设定、不能遗忘的人物状态

### 步骤 2：写正文

根据任务卡的指引，写出第 1 章的 `.txt` 文件，放到对应位置：

```
novels/<小说slug>/第01卷/第1章_开篇.txt
```

（如果不确定路径，运行 `python novel.py demo` 看一次示例。）

### 步骤 3：post —— 跑门禁 + 入库

```bash
python novel.py post 1
```

这会运行全部 21 个门禁检查：
- 连续性：上一章的状态有没有被遗忘
- 反 AI 腔：有没有"总之""综上所述""缓缓开口"等模板句
- 场景推进：这一章有没有真的发生事件
- 追读力：钩子、悬念、爽点是否到位
- 标点：破折号/感叹号有没有滥用
- ……

如果发现严重问题，门禁会报 WARNING 或 FAIL。

### 步骤 4：生成 Story 提交记录（可选）

```bash
python novel.py post 1 --story
```

这会自动生成一篇 `.story/commits/chapter_001_commit.json`，记录本章的关键信息，供后续章节参考。

### 步骤 5：查看报告

```bash
python novel.py report
```

列出最近生成的门禁报告，告诉你哪些章节通过了、哪些有问题。

---

## 8. 审稿（jury / agents）

写完一章后，可以让 AI 审稿团帮你审稿：

```bash
# 轻量审稿（单 Agent 快速扫描）
python novel.py agents review 1

# 完整审稿（8 Agent 并行）
python novel.py agents review 1 --mode full
```

8 个 Agent 分别从：
- 对话节奏
- 场景因果
- 人物口吻
- 文风变化
- 追读力
- 连续性
- 反 AI 腔
- 合规自查

多维度打分，Chief Editor 汇总综合评分。**审稿不覆盖正文，只出报告。**

---

## 9. 管理 DB 工作区和大纲

### 工作区管理

```bash
# 列出所有工作区
python novel.py db list

# 显示当前工作区
python novel.py db current

# 查看工作区详情
python novel.py db info

# 创建新工作区
python novel.py db new --name "第二本小说"

# 切换工作区
python novel.py db use slot_002

# 备份当前工作区
python novel.py db backup

# 删除工作区（不能删除当前活跃的）
python novel.py db delete slot_005
```

### 大纲管理

```bash
# 添加大纲
python novel.py outline add 大纲.txt

# 导入大纲（指定标题）
python novel.py outline import 大纲.txt --title "我的小说"

# 列出当前工作区所有大纲
python novel.py outline list

# 查看当前激活大纲
python novel.py outline current

# 切换大纲
python novel.py outline switch <outline_id>

# 对比两个大纲
python novel.py outline diff <id1> <id2>

# 对比文件与当前大纲
python novel.py outline compare 另一份大纲.txt

# 回滚大纲到上一个版本
python novel.py outline rollback <outline_id>

# 删除大纲
python novel.py outline delete <outline_id>
```

### 版本回滚

每次更新大纲时，引擎会自动保存一个版本快照。回滚后可以恢复到之前的版本：

```bash
python novel.py outline rollback <outline_id>
```

回滚后显示：
```
  ✅ 已回滚大纲「青云问道」到版本 v3
  保存时间: 2026-05-25 14:30:00
  剩余历史版本: 2
```

---

## 10. 大纲的相似度检测

添加大纲时，引擎会自动检测新大纲与当前激活大纲的相似度。检测维度包括：

| 维度 | 权重 | 说明 |
|------|------|------|
| 标题相似度 | 15% | Levenshtein 编辑距离 |
| 角色名重叠 | 25% | 提取中英文人名，计算重叠率 |
| 世界观关键词 | 25% | 识别修炼体系、宗派、世界设定等关键词 |
| 章节结构 | 15% | 章节数、卷数是否接近 |
| 题材/风格 | 20% | 修仙/都市/科幻等题材标签是否一致 |

### 分类结果

| 相似度范围 | 分类 | 建议 |
|-----------|------|------|
| ≥70 | 高相似度 | 建议升级（同一部小说的新版本） |
| 35–69 | 不确定 | 根据角色/世界观细节进一步判断 |
| <35 | 低相似度 | 可能是不同小说，建议新建工作区 |

### 手动对比

你也可以随时对比两个大纲：

```bash
python novel.py outline diff <id1> <id2>
```

输出示例：

```
  大纲对比: [青云问道_20260526120000] 青云问道  vs  [都市重生_20260526120100] 都市重生

  📊 综合相似度: 12/100
  🏷️  分类: 低相似度
  💡 建议: 可能是不同小说

  各维度明细:
  --------------------------------------------------
  标题相似度:      15.0分  (权重15%)
  角色名重叠:      0.0分  (权重25%)
    共同角色: (无)
  世界观重叠:      5.0分  (权重25%)
    共同关键词: (无)
  章节结构相似:    30.0分  (权重15%)
  题材/风格重叠:   10.0分  (权重20%)
```

---

## 11. 常用命令速查

```bash
# 初始化
python novel.py init                    # 初始化项目
python novel.py status                  # 健康检查

# Demo
python novel.py demo                    # 跑通完整 demo 流程

# 工作区
python novel.py db init                 # 初始化 workspace
python novel.py db list                 # 列出所有工作区
python novel.py db new --name "名称"    # 创建新工作区
python novel.py db use <slot_id>        # 切换工作区
python novel.py db info                 # 查看工作区详情

# 大纲
python novel.py outline add <文件>      # 添加大纲（自动相似度检测）
python novel.py outline import <文件> --title "标题"   # 导入大纲
python novel.py outline list            # 列出所有大纲
python novel.py outline current         # 查看当前大纲
python novel.py outline switch <id>     # 切换大纲
python novel.py outline diff <id1> <id2>  # 对比两个大纲
python novel.py outline compare <文件>  # 与文件对比
python novel.py outline rollback <id>   # 回滚大纲

# 写作流程
python novel.py pre 1                   # 写前任务卡
# → 写正文 → 
python novel.py post 1                  # 写后门禁 + 入库
python novel.py post 1 --story          # 门禁 + 生成 story 提交
python novel.py report                  # 查看报告

# 审稿
python novel.py agents review 1         # 轻量审稿
python novel.py agents review 1 --mode full   # 完整审稿

# 其他
python novel.py wc 1                    # 统计第1章字数
python novel.py board                   # 项目看板
python novel.py story init              # 初始化故事链
python novel.py story contract 1        # 生成章节合同
python novel.py story commit 1          # 生成提交记录
python novel.py story health            # 故事链健康检查
```

---

## 快速开始（5 分钟体验完整流程）

```bash
# 1. 安装 + 初始化
pip install -r requirements.txt
python novel.py init

# 2. 创建工作区
python novel.py db new --name "我的小说"

# 3. 创建并添加大纲（先用 demo 自带的样例）
echo "# 我的小说大纲" > my_outline.txt
echo "" >> my_outline.txt
echo "第一卷：开篇" >> my_outline.txt
echo "第1章：主角登场" >> my_outline.txt
echo "第2章：冲突开始" >> my_outline.txt
python novel.py outline add my_outline.txt

# 4. 查看大纲
python novel.py outline current

# 5. 生成写前任务卡
python novel.py pre 1

# 6. （手动写第1章正文，放到对应目录）
# novels/<slug>/第01卷/第1章*.txt

# 7. 入库
python novel.py post 1

# 8. 审稿
python novel.py agents review 1

# 9. 查看报告
python novel.py report
```

---

## 遇到问题？

- 先跑 `python novel.py status` 确认环境正常
- 确认 `config.json` 存在且配置正确
- 确认大纲已添加且激活（`python novel.py outline current`）
- 查看项目 [README.md](../README.md) 和 [CHANGELOG.md](../CHANGELOG.md)
