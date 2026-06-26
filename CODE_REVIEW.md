# ProseForge 代码审查报告

> ⚠️ **复核更新**：P0 #1（三文件截断）已失效——提交 `3f9dfdd` 已重写那三个文件，现编译/import 全通过、285 测试绿。逐条复核见文末「复核结论」。

审查日期：2026-06-25 · 范围：核心内核（`src/runtime.py`、`src/db/`、`src/pipeline/`、`src/guards/`、`src/agents/`、`src/rag/`、相关 `src/utils/`）· 方法：逐文件读真实代码 + `py_compile` / import 冒烟验证。

本报告只读、不改动任何文件。每条 P0/High 都给出了验证方式和修复建议。

---

## 总评

架构设计是这套系统最扎实的部分：守卫系统有单一注册中心（`guard_registry.py`），`GuardResult/GuardSummary` 是干净的 dataclass 数据模型，`_cluster_aggregator` 和 `run_single_guard` 都做了子检测隔离，`connect_sqlite` 统一了 WAL/超时/外键，`write_json_atomic` 用了 temp+rename，RAG 的 RRF 融合实现正确，config 归一化很防御性。整体"一个内核两入口三表面"的分层是清晰且自洽的。

但当前**工作区里有一个 P0 级阻断问题**：三个文件被截断，导致整条流水线根本无法 import。除此之外还有几个真实的健壮性/并发隐患，以及一批可维护性坏味道。

严重程度统计：**P0 阻断 1 · 高 3 · 中 6 · 低 9**。

---

## P0 — 阻断（必须先修）

### 1. 三个工作区文件被截断，pipeline 无法 import

`src/db/init_db.py`、`src/db/slot_manager.py`、`src/pipeline/_base.py` 在当前工作树中都被**截断在一行的中间**（分别停在 `cont`、`sel`、`volume_`），且都是 CRLF 行尾。这是文件同步/写入被中途打断的典型特征，不像人为编辑。

后果（已实测验证）：

- `src/db/init_db.py`：丢失了 `run_migrations` 的尾部和**整个 `init_db()` 函数**。`from src.db.init_db import init_db` → `ImportError`，`slot_manager` 连带无法导入 → `nf_project` / `nf_pipeline` 全部失效。
- `src/pipeline/_base.py`：第 238 行 `(` 未闭合 → `SyntaxError`，`src.pipeline.pre` / `post` 直接无法 import。
- `src/db/slot_manager.py`：`switch_to()` 被截断，丢失尾部约 14 行。

验证：

```
$ python3 -m py_compile src/pipeline/_base.py   →  SyntaxError: '(' was never closed (line 238)
$ python3 -c "from src.db.init_db import init_db" →  ImportError: cannot import name 'init_db'
$ git diff --stat HEAD
  src/db/init_db.py      | 80 +-----  (79 行被删)
  src/db/slot_manager.py | 15 +----
  src/pipeline/_base.py  | 18 +----
```

`git HEAD` 里这三个文件是完整且能编译的——也就是说损坏只发生在未提交的工作树副本里。

**修复**：从 HEAD 恢复即可（仓库已有完整版本）：

```bash
git checkout -- src/db/init_db.py src/db/slot_manager.py src/pipeline/_base.py
```

恢复后建议立刻跑 `python -m pytest tests/ -x -q` 确认 ~280 项测试回绿。

---

## 高（High）

### 2. ingest 把外部内容 FTS5 表当普通表用，rowid 契约被破坏

`src/pipeline/ingest.py` 里 `novel_chunk_fts` 声明为外部内容表（`content='chapter_chunks', content_rowid='id'`），但插入时用的是**合成 rowid** `ch_id*10000 + cno`，并不等于 `chapter_chunks.id`：

```python
cur.execute("INSERT INTO novel_chunk_fts(rowid,content) VALUES(?,?)",
            (ch_id * 10000 + cno, ctext))
```

外部内容 FTS5 期望 rowid 与基表 `content_rowid` 一致，否则 `'rebuild'` 命令会按基表重建、把这些合成行全部抹掉。这很可能正是 `pre.py` / `post.py` 里需要反复做"FTS 健康检查 + 自动 repair"的根因——FTS 在和自己打架。建议二选一：要么把这些 FTS 表改成**非**外部内容表（`content=''`，自己全权管理 rowid），要么让 rowid 真正对齐基表 id 并用触发器维护。`novel_chapter_fts` 用 `rowid=ch_id` 是对齐 `chapters.id` 的，没问题；问题集中在 chunk 表。

### 3. `pre.py` 全程持有一个写连接，且无 try/finally

`run_pre()`（约 750 行）在第 89 行 `conn = connect(app)` 打开一个 WAL **写**连接，直到第 789 行才 `conn.commit(); conn.close()`。期间夹着文件 I/O、YAML 解析、RAG 检索、deviation 评分等大量耗时操作。两个问题：

- 没有 `try/finally` 包裹——中途任何未被局部捕获的异常都会让连接（和写锁）泄漏。
- 长时间持有写锁，与 `_conn.py` 注释里宣称的"支持 pre/post/ingest 多进程并发"直接矛盾；批量写作时极易 `database is locked`。

建议：缩短连接生命周期（读完即关），或至少用 `try/finally` 兜底关闭。

### 4. registry.json / project.json 写入既不原子也无锁

`src/db/registry.py` 的 `save()` 和 `SlotManager` 各处都用裸 `write_text()` 写 JSON，没有 temp+rename，也没有任何文件锁。但项目本身已经有 `write_json_atomic`（`_base.py`），却没用在这里。后果：

- 写到一半崩溃 → `registry.json` 损坏，整个 workspace 失去 active_slot 指向。
- 并发 `load → 改 → save` 是读改写竞态 → 丢更新。

这同样和"多进程并发"的设计目标冲突。建议 registry/project 的所有写入都改走 `write_json_atomic`，并视需要加进程锁。

---

## 中（Medium）

### 5. 审读"分数"方向是反的，且对外没说明

`base_agent.py` 注释明确写着 score「higher = more issues (lower quality)」，即**分数越高越差**。但 `orchestrator.py` 把它平均成 `overall_score`，`post.py` 又打印成 `[REVIEW] full mode: score {N}`。读者自然会理解成"越高越好"，与实际含义相反。建议要么反转为"质量分"，要么在所有输出处显式标注"问题分，越低越好"。

### 6. 去重的"多来源交叉确认"在 v0.8.0 后基本失效

`report_deduplicator.deduplicate_warnings` 对归类问题要求 `len(sources) >= 2 or avg_conf > 0.7` 才合并。但 v0.8.0 后 warning 的 `guard` 字段已是 L2 聚合名（如 `prose_authenticity_guard`），子检测身份在 `get_warnings()` 这条路径上丢失，于是 `sources` 几乎恒为 1 个——"≥2 个门禁共同发现"这条规则几乎永不触发，只剩 `avg_conf > 0.7` 在起作用。代码注释里承认了身份丢失，但没有解决其对去重逻辑的削弱。建议在 finding 里保留 `source_guard` 并让去重按子检测名统计来源。

### 7. 大量 `except Exception` 静默吞错，"质量门禁"可无声空转

`post.py` 的质量层、以及众多 human_texture 守卫（例如 `voice_diversity_guard.py` 有约 25 处 `except Exception:`）普遍是"出错就 print 一句 WARN / 直接 pass"。叠加 `run_single_guard` 的 fail-open（守卫崩溃→降级 WARN）和 L2「永不 FAIL」规则，最终**真正能 BLOCK 的只剩 L1 与 L3 合规**，而且前提是它们不崩。一个守卫有 bug，效果就是悄悄不设防、ingest 照常进行。fail-open 作为设计取向可以接受，但应至少把崩溃聚合到 summary 里显式计数告警，而不是埋在 stdout。

### 8. `post.py` genre 兜底分支的连接泄漏

```python
try:
    conn3 = connect_sqlite(app.db_path)
    ...
    conn3.close()
except Exception:
    pass
```

`conn3.close()` 在 try 内部——一旦 `execute/fetchone` 抛错，`close()` 被跳过，连接泄漏。应放进 `finally` 或用 `with closing(...)`。

### 9. 两套审查系统的失败哲学相反且未说明

守卫系统是 fail-open（崩溃→WARN，不阻断）；而 `orchestrator.py` 的 agent 审读对崩溃的 agent 赋 `status=FAIL, score=100`，进而把 `overall_status` 推成 FAIL（fail-closed）。两种相反策略混在一个系统里，且没有文档说明，调用方很容易困惑。建议统一或在文档里明确区分。

### 10. 超长函数，难测难维护

`run_post`（约 400 行）和 `run_pre`（约 750 行）各自把字数门禁、FTS、精神触发词、守卫编排、human_texture、去重、ingest、审读、改稿检测全塞在一个函数里。圈复杂度高、嵌套 try 多、几乎无法做单元测试。建议按步骤拆成可独立测试的小函数。

---

## 低（Low）/ 坏味道

11. **`if wc_pass == False:`**（`post.py`）——应为 `is False`；同处变量 `candidates` 实际是单个 `Path`，命名误导。
12. **死代码**：`post.py` human_texture 块里把 `_pipeline_genre` 重新从 state 读一遍后赋空串，随即用的是 `genre = selected_genre`，那段重算没有任何作用。
13. **`_find_chapter_file` 返回 `glob(...)[0]`**——多个文件命中同一章时顺序由文件系统决定，非确定性。
14. **`GuardSummary.version = get_version()`** 作为 dataclass 默认值，在 import 时求值一次（当前静态版本号无碍，但属于已知陷阱模式）。
15. **`registry.is_initialized()`** 要求存在 `version` 键，而 `load()` 的缺省 dict 不含该键；`get_next_slot_id()` 标了 DEPRECATED 却仍被 `create_slot_auto` 调用。
16. **f-string 拼表名/列名的动态 SQL**（`fts_health.py` 多处、`voice_diversity_guard.py:412`）——目前表名来自 `sqlite_master`、列名来自白名单 `col_map`，值都用占位符，**当前无注入风险**；但模式依赖"输入可信"，若将来接入外部输入需加固或注释说明。
17. **ingest 标题正则** `第\d+章_(.+)\.txt` 期望下划线命名，而文件其实按 `第N章*.txt` 落盘 → `title_match` 多半为 None，标题总是回退到 `stem`。
18. **两条删除路径**：`delete_slot`（硬删 `rmtree`）与 `delete_slot_safe`（移入回收站）并存，硬删绕过回收站，存在冗余与误删风险。
19. **角色出场/世界设定提及用 `content.count(name)` 子串统计** → 短名或常见字（如单字姓名）会误计、串到别的词里。

---

## 做得好的地方

- `guard_registry.py` 作为唯一注册中心，L1/L2/L3 分级 + 模式派发 + 「L2 永不 FAIL」集中实现，职责清晰。
- `GuardResult` / `GuardSummary` / `GuardFinding` 数据模型干净，`get_warnings()`、`compute()`、`save/load` 完整自洽。
- `_cluster_aggregator._run_subcheck` 与 `run_single_guard` 都做了子检测/守卫级异常隔离，单点失败不拖垮整盘。
- `connect_sqlite` 统一 WAL+timeout+外键、只读走 `mode=ro`；`write_json_atomic` 用 temp+`os.replace`。
- `config_utils.normalize_config` 大量 `setdefault` 兜底，下游少踩 `None.get()`。
- `init_db` 家族的 schema/migration 幂等设计（`IF NOT EXISTS` + `schema_migrations` 去重）合理；slot 按书名 slug 命名、空 title 强制时间戳后缀避免互相覆盖，考虑周到。
- `pre.py` 用的是**具体异常类型**而非裸 `except`，明显优于 `post.py`。
- RAG 的 RRF 融合公式实现正确，向量依赖缺失时优雅降级为纯 FTS5。

---

## 建议处理顺序

1. **立即**：`git checkout` 恢复 3 个被截断文件（P0 #1），跑测试回绿。
2. **近期**：修 FTS 外部内容 rowid 契约（#2）、`pre.py` 连接生命周期与 `try/finally`（#3）、registry 原子写（#4）。
3. **中期**：统一/澄清失败哲学与分数方向（#5/#9），让守卫崩溃在 summary 里显式可见（#7），修连接泄漏（#8）。
4. **持续**：拆分超长函数（#10），清理低优坏味道（#11–#19）。

---

## 复核结论（2026-06-25 · against HEAD `3e26754` · 不改代码）

逐条对照当前真实代码核验（file:line 为现行行号）。本轮仅复核、未改任何代码。

| 编号 | 结论 | 证据 |
|------|------|------|
| **P0 #1** 三文件截断 | **已失效/已修复** | `py_compile` + import 全过；提交 `3f9dfdd` 重写 `init_db.py`/`slot_manager.py`/`_base.py`，285 测试绿。报告快照的是工作树被截断的瞬态。 |
| **High #2** FTS rowid 契约 | **✅ 已修复（本批）** | `ingest.py` 改用真实 `chapter_chunks.id`（`cur.lastrowid`）作 FTS rowid，重灌走外部内容 `'delete'` 命令；RAG 分块富化与 rebuild churn 一并修复。 |
| **High #3** pre 连接生命周期 | **✅ 已修复** | `run_pre` 业务体包进 `try/finally`：`conn.commit()` 在 try 末，`conn.close()` 在 finally，异常路径保证关连接；state 保存/return 在 try 外（本就不用 conn）。行为不变，295 测试绿。 |
| **High #4** registry 非原子写 | **✅ 已修复（本批）** | `write_json_atomic` 下沉到 `src/utils/json_io.py`，`registry.save` + slot 4 处 JSON 写改原子写。 |
| **Med #5** 分数方向反 | **✅ 已修复** | 输出显式标注"问题分/越低越好"：`post.py` 打印 `issue-score`，orchestrator 报告加 `score_direction: lower_is_better`（不反转数值，避免动消费方）。 |
| **Med #6** 去重交叉确认失效 | **⃝ 实测已满足** | 复核发现现行代码 `_adapt_legacy_dict:147` 已把子检测名写入 `source_guard` 并直达去重（`run_orchestrated` 用 `get_warnings()`）；实测两子检测合并、`reported_by` 为 2 个来源。报告结论已过时；加回归测试 `test_dedup_counts_distinct_subcheck_sources` 锁定。 |
| **Med #7** 静默吞错 | **✅ 已修复（记账）** | `GuardSummary.crashed_guards` 显式收集崩溃降级的 guard，save/load 往返，post 打印 `[WARN] N guard(s) 崩溃→降级 WARN`。fail-open 保留为设计，但失防现在可见。 |
| **Med #8** conn3 泄漏 | **✅ 已修复** | `post.py` 改用 `with closing(connect_sqlite(...))`。 |
| **Med #9** 两套失败哲学相反 | **✅ 已修复（文档）** | `docs/architecture.md` 设计决策 #7 明确 guards fail-open vs agents fail-closed 的取向、原因与分数方向。 |
| **Med #10** 超长函数 | **✅ 已修复** | `run_pre` 750→153 行（22 个小函数）；`run_post` 435→123 行（13 个小函数：state/fts/mental/genre/word-count/prev-brief/extra-context/orchestrator/texture/dedup/track/agent-review/fixes），嵌套 try 的 fail-open 隔离严格保留。先补端到端特征测试 `test_post_pipeline.py` 锁定行为再拆。行为与 stdout 不变，315 测试绿。 |
| **Low #11** `== False` | **✅ 已修复** | `post.py` 改 `is False`；误导变量 `candidates`→`chapter_file`。 |
| **Low #12** 死代码 | **✅ 已修复** | 删除 human_texture 块里被丢弃的 `_pipeline_genre` 重算。 |
| **Low #13** 非确定 glob | **✅ 已修复** | `_find_chapter_file` 改 `sorted(glob(...))[0]`。 |
| **Low #14** dataclass 默认 | **✅ 已修复** | `GuardSummary.version` 改 `field(default_factory=get_version)`。 |
| **Low #15** 弃用/初始化键 | **✅ 已修复** | 删除未用的 `create_slot_auto`/`get_next_slot_id`；`is_initialized` 不再依赖 `version` 键。 |
| **Low #17** 标题正则 | **真实但被缓解** | `ingest.py:61` 下划线正则多半 None，但 `:68` 有正文 `# 第N章 标题` 兜底，标题未必退化到 stem。 |
| **Low #18** 两条删除路径 | **✅ 已修复** | `delete_slot` 默认改走回收站（`delete_slot_safe`），仅 `force=True` 永久硬删；统一入口、消除误删风险。 |
| **Low #16** 动态 SQL | **✅ 已修复（加固）** | `fts_health.py` 加 `_safe_ident` 标识符护栏，在 `find_fts5_tables` + `safe_fts_search` 所有 f-string 插值点校验表名/列名；`voice_diversity_guard.py` 注明 `col` 由 `col_map` 白名单保证。无注入风险的隐含假设变显式断言。 |
| **Low #19** 子串误计 | **接受（维持现状）** | `content.count(name)` 中文无词边界，真正修复需分词、成本高易回归；维持现状（短名/常见字可能误计为已知局限）。 |

**净结论**：除 P0 已失效外，其余 High/Medium/Low 均在现行代码中成立。本轮不改代码，留待后续按报告「建议处理顺序」分批修复。
