# 数据库 Schema

基于 SQLite 3，单文件 `hermes_memory.db`，15 张表分为三层。

## 一、通用记忆底座

### memories（核心记忆表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 主键 |
| type | TEXT | 记忆类型: preference/project/task/code/deployment/rule/summary/note/system |
| project | TEXT | 所属项目 |
| title | TEXT | 标题 |
| content | TEXT | 内容 |
| tags | TEXT | 标签 |
| importance | INTEGER | 重要性 1-5 |
| source | TEXT | 来源 |
| status | TEXT | active/archived/deprecated |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |
| last_used_at | TEXT | 最后使用时间 |

### memory_fts（FTS5 全文检索）

```sql
CREATE VIRTUAL TABLE memory_fts USING fts5(
    title, content, tags,
    content='memories', content_rowid='id'
);
```

含 INSERT/UPDATE/DELETE 自动同步触发器。

### projects / settings / memory_logs

- `projects`: id, name, description, status, created_at, updated_at
- `settings`: key (PK), value, updated_at
- `memory_logs`: id, action, target_type, target_id, detail, created_at

## 二、小说业务层

### novels（小说项目）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| slug | TEXT UNIQUE | 英文标识 |
| title | TEXT | 书名 |
| genre | TEXT | 类型 |
| theme | TEXT | 主题 |
| description | TEXT | 简介 |
| target_words | INTEGER | 目标字数 |
| current_words | INTEGER | 当前字数 |
| status | TEXT | planning/writing/completed |

### volumes（分卷）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | → novels.id |
| volume_no | INTEGER | 卷号 |
| title | TEXT | 卷名 |
| summary | TEXT | 摘要 |
| target_words | INTEGER | 目标字数 |

### chapters（章节）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | |
| volume_id | INTEGER FK | → volumes.id |
| chapter_no | INTEGER | 章节号 |
| title | TEXT | 标题 |
| content | TEXT | 正文 |
| summary | TEXT | 摘要 |
| word_count | INTEGER | 字数 |
| status | TEXT | draft/revised/final |
| file_path | TEXT | TXT 文件路径 |

### chapter_chunks（章节切片）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | |
| chapter_id | INTEGER FK | → chapters.id |
| chunk_no | INTEGER | 切片序号 |
| content | TEXT | 切片内容 (800-1500字) |
| word_count | INTEGER | 字数 |

切片规则：按自然段落切分，每片 800-1500 字，不打散完整句子。

### characters（人物）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | |
| name | TEXT | 姓名 |
| alias | TEXT | 别名 |
| role | TEXT | 男主/女主/配角/反派 |
| identity | TEXT | 身份 |
| personality | TEXT | 性格 |
| motivation | TEXT | 动机 |
| ability | TEXT | 能力 |
| relationship | TEXT | 关系 |
| arc | TEXT | 角色弧线 |
| status | TEXT | active/dead/retired |
| tags | TEXT | 标签 |

### worldbuilding（世界观）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | |
| category | TEXT | 修炼体系/物理法则/宗门势力/地理地点/历史背景/法宝丹药/功法术法/社会制度/禁忌规则/其他 |
| title | TEXT | 标题 |
| content | TEXT | 内容 |
| importance | INTEGER | 1-5 |
| tags | TEXT | 标签 |

### plot_threads（伏笔追踪）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | |
| title | TEXT | 标题 |
| content | TEXT | 内容 |
| thread_type | TEXT | 伏笔/剧情线/悬念 |
| introduced_chapter | INTEGER | 引入章节 |
| resolved_chapter | INTEGER | 回收章节 |
| status | TEXT | open/active/resolved/abandoned |
| importance | INTEGER | 1-5 |

### writing_rules（写作规则）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | |
| title | TEXT | 规则名 |
| content | TEXT | 规则内容 |
| rule_type | TEXT | style/structure/pacing/character/world/forbidden/continuity/other |
| importance | INTEGER | 1-5 |
| status | TEXT | active/archived |

### chapter_summaries（章节摘要）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | |
| chapter_id | INTEGER FK | |
| short_summary | TEXT | 短摘要 (100-200字) |
| long_summary | TEXT | 长摘要 (500-800字) |
| key_events | TEXT | 关键事件 |
| characters_involved | TEXT | 出场人物 |
| new_settings | TEXT | 新设定 |
| foreshadowing | TEXT | 伏笔变化 |
| continuity_notes | TEXT | 连续性备注 |

### continuity_checks（连续性检查）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | |
| chapter_id | INTEGER FK | |
| check_type | TEXT | 检查类型 |
| issue | TEXT | 问题描述 |
| suggestion | TEXT | 修复建议 |
| severity | INTEGER | 严重度 1-5 |
| status | TEXT | open/resolved |

### novel_logs（操作日志）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| action | TEXT | pre_write/ingest/search_before_write/stage_review |
| target_type | TEXT | chapter/character/plot_thread |
| target_id | INTEGER | |
| detail | TEXT | 详细信息 |
| created_at | TEXT | |

## 三、版本与承诺

### chapter_versions（版本快照）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | |
| chapter_id | INTEGER | |
| chapter_no | INTEGER | |
| version_no | INTEGER | 版本号 (自增) |
| version_status | TEXT | draft/expanded/revised/checked/final/deprecated |
| title | TEXT | |
| content | TEXT | 全文快照 |
| word_count | INTEGER | |
| change_reason | TEXT | 变更原因 |
| created_at | TEXT | |

**规则：** 旧版本不物理删除，只标记 `deprecated`。每次 `ingest` 自动保存新版本。

### reader_promises（读者承诺）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| novel_id | INTEGER FK | |
| promise_title | TEXT | 承诺标题 |
| promise_detail | TEXT | 详细内容 |
| introduced_chapter | INTEGER | 建立章节 |
| expected_payoff_range | TEXT | 预期兑现范围 |
| payoff_chapter | INTEGER | 实际兑现章节 |
| status | TEXT | open/delayed/paid/abandoned |
| importance | INTEGER | 1-5 |
| reader_emotion | TEXT | 期待/悬念/爽点/仇恨/打脸/成长/危机/感动 |

## 四、FTS5 全文检索索引

| 索引表 | 覆盖基础表 | 同步方式 |
|--------|-----------|----------|
| `memory_fts` | memories | 触发器自动 |
| `novel_chapter_fts` | chapters | 手动（ingest 时同步） |
| `novel_chunk_fts` | chapter_chunks | 手动（ingest 时同步） |
| `novel_character_fts` | characters | 触发器自动 |
| `novel_world_fts` | worldbuilding | 触发器自动 |
| `novel_plot_fts` | plot_threads | 触发器自动 |

FTS5 检索失败时自动回退到 SQL `LIKE` 查询。
