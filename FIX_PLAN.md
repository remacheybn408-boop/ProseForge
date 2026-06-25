# ProseForge 修复计划

## 背景

ProseForge 是一个公开项目，但存在以下问题导致无法从 git clone 后直接使用：

1. `database/schema.sql` 从未提交到 git —— 致命
2. `database/migrations/` 也不在 git 中
3. `schema.sql` 表定义不全
4. 14 个测试失败
5. `.gitignore` 未覆盖所有产物目录

以下为逐项修复步骤，按顺序执行。

---

## 步骤 1：提交 database/schema.sql

### 说明
`SlotManager._init_slot_db()` 要求 `database/schema.sql` 存在才能创建 slot DB。该文件从未被 git 跟踪。

### 操作
```bash
git add database/schema.sql
git commit -m "fix: add missing database/schema.sql — core file required by SlotManager._init_slot_db"
```

### 验收
```
python -c "
from src.db.slot_manager import SlotManager
from pathlib import Path
root = Path.cwd()
# 测试用临时目录，不在 workspace 内生产
import tempfile, os
tmp = Path(tempfile.mkdtemp())
result = SlotManager(root).create_slot('test_verify')
print('OK:', result)
SlotManager(root).delete_slot_safe('test_verify', confirm=True)
```
不抛 `FileNotFoundError` 即通过。

---

## 步骤 2：补全 schema.sql 表定义

### 说明
当前 schema.sql 只有 14 张表。测试期望以下表也存在，但它们从未被创建（migration 文件也未存在过）：

```
voice_packs
character_voice_examples
character_voice_observations
character_voice_history
title_history
chapter_summaries
chapter_contexts
arc_character_states
continuity_checks
memories
novel_logs
writing_rules
```

### 操作
1. 找到参考来源：`workspace/认出曾经的王/novel.db` 中有完整 schema
2. 从该 DB dump DDL，提取上述缺失表的 `CREATE TABLE IF NOT EXISTS` 语句
3. 追加到 `database/schema.sql` 末尾（不要删除已有内容）
4. 验证：

```bash
python -m pytest tests/test_schema_init.py tests/test_voice_memory_schema.py -v
```
预期全部 PASS。

5. 提交：
```bash
git add database/schema.sql
git commit -m "fix: complete schema.sql with all required tables (voice/meta/continuity)"
```

---

## 步骤 3：补 database/migrations/ 目录

### 说明
`find_migrations()` 查找 `database/migrations/` 目录。该目录不存在于 git 中。当前不需要真正的 migration 文件，但目录结构必须在。

### 操作
```bash
mkdir -p database/migrations
touch database/migrations/.gitkeep
git add database/migrations/.gitkeep
git commit -m "chore: add database/migrations/ structure with .gitkeep"
```

---

## 步骤 4：更新 .gitignore

### 说明
确保以下目录不会被提交。

### 操作
编辑 `.gitignore`，确认包含：

```
# ProseForge working directories
workspace/
data/
novels/
outputs/
tmp/
大纲/

# Runtime config (local overrides)
config.json

# Secrets
config/license_server.json

# Python
*.pyc
__pycache__/
```

```bash
git add .gitignore
git commit -m "chore: update .gitignore for workspace and output directories"
```

---

## 步骤 5：修剩余测试失败

### 说明
完成步骤 1-4 后，用以下命令确认剩余失败：

```bash
python -m pytest tests/ -q --tb=line 2>&1 | tail -40
```

当前已知失败中有约 8 个是 Phase 1-3 修完后会自动过的（schema 相关）。剩余失败需要逐一定位：

### 5.1 如果 test_init_db_applies_real_migrations 还失败
原因是 `find_migrations()` 找不到 migration 文件。如果步骤 3 已执行但目录内无 `.sql` 文件，这个测试会报错。解决方案：在 `database/migrations/` 下创建一个空 migration 文件或者修复测试让它接受空目录。

### 5.2 如果 test_check_fts_health_* 失败
FTS health check 逻辑可能对 FTS 表结构有额外验证（如 FTS content表中必需的列）。需要检查 `src/db/fts_health.py`，确认其对 `novel_chapter_fts`、`novel_chunk_fts` 等索引的验证条件。

### 5.3 如果 test_full_ch1_cycle 失败
端到端 pipeline 测试。失败原因可能是：
- chunk 拆分逻辑依赖预置数据
- 或 `_base.py` 中的配置加载有问题
需要检查测试内 mock 数据和实际 pipeline 代码之间的接口对齐。

### 5.4 如果 test_volume_post_generates_report 失败
volume post 流程。检查 `src/pipeline/volume.py` 中的报告生成逻辑是否依赖了缺失的 migration 表。

### 5.5 如果 test_run_accept_ingest_appends_snapshot 失败
rewrite/accept 流程。检查 `src/pipeline/rewrite.py` 和 `src/pipeline/post.py` 中的版本快照逻辑。

---

## 步骤 6：最终验证

```bash
# 1. 从零跑测试
python -m pytest tests/ -q --tb=short 2>&1

# 2. 验证能创建 slot
python -c "
from src.db.slot_manager import SlotManager
from pathlib import Path
sm = SlotManager(Path.cwd())
s = sm.create_slot('ci_verify')
sm.switch_to('ci_verify')
print('Slot creation: OK')
sm.delete_slot_safe('ci_verify', confirm=True)
print('Slot cleanup: OK')
"

# 3. 验证能导入大纲
python -c "
from src.outline.outline_manager import OutlineManager
from pathlib import Path
mgr = OutlineManager(Path.cwd())
result = mgr.add_outline(
    content='# 测试大纲\n这是一个测试。',
    title='测试小说',
    genre='测试',
    style='测试',
    tags=['test']
)
print('Outline import:', result.get('status'))
"

# 4. 确认无未跟踪的产物文件
git status --short | grep -v '^?? database/schema.sql'
# 应无输出（或只有符合预期的文件）
```

---

## 提交结构

```
fix: add missing database/schema.sql — core file required by SlotManager._init_slot_db
fix: complete schema.sql with all required tables (voice/meta/continuity)
chore: add database/migrations/ structure with .gitkeep
chore: update .gitignore for workspace and output directories
fix: [每步5的子项逐个提交]
```

不要 squash 到一个 commit。每步单独提交，方便 review。
