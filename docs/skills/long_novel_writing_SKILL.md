# 长篇小说连续写作 Skill

> 通用版：已移除具体小说名、专属设定名、卷名和角色名。

# 0. Skill Router 优先规则

**任何长篇小说任务开始前，必须先读取 docs/skills/novel_factory_router_SKILL.md 进行模式路由。**

本 Skill 必须先读取 docs/skills/novel_factory_router_SKILL.md。

当用户当前指令属于正文写作类任务时，必须进入 NOVEL_WRITE_MODE，并调用 novel-factory skill。

正文写作类任务包括：

- 写第 N 章
- 写正文
- 续写
- 继续写
- 下一章
- 写完本卷
- 继续整本书
- 根据 task_card 写
- 从上一章继续

此时，本 Skill 中"当前唯一任务是标题骨架"的规则不再拦截正文任务。

"标题骨架优先"只在以下情况生效：

1. 用户明确要求生成标题骨架。
2. 用户明确要求做全书规划。
3. 用户明确要求补 volume_plans / chapter_plans。
4. 用户没有要求写正文。

禁止：

1. 用户要求写正文时，转去做标题骨架。
2. 用户要求写正文时，转去做审计报告。
3. 用户要求写正文时，转去扩容 pipeline。
4. 用户要求写正文时，用普通聊天模式代替 novel-factory。

版本：V1.0
用途：供 Hermes Agent / 写作 Agent 执行长篇小说连续创作、章节规划、上下文承接、入库闭环使用。
适用范围：玄幻、都市、科幻、仙侠、言情、历史、悬疑等长篇连载小说。
核心目标：防止跳卷、断章、缩水、停顿、只看大纲写、上下文断裂、系统扩容干扰正文推进。

============================================================
一、最高优先级原则
============================================================

1. 写作主线优先级高于系统扩容。
2. 按卷顺序完成优先级高于临时讨论。
3. 当前卷未完成，禁止跳到下一卷。
4. 当前卷未完成，禁止跳到后面任意卷。
5. 当前章 post / ingest 通过后，必须立刻 pre 下一章。
6. 当前卷最后一章 post / ingest / volume_post 通过后，必须立刻 pre 下一卷第 1 章。
7. 不允许习惯性停顿问：
   - 继续吗？
   - 要不要修整？
   - 是否进入下一章？
   - 是否进入下一卷？
8. 除非用户明确下达“暂停 / 复盘 / 修改 / 停止 / 重写”指令，否则默认继续按顺序推进。
9. 用户要求“写完某一卷”时，这是死命令，不是可商量对话。
10. 用户要求“继续写整本书”时，默认按卷序从当前章一路推进。
11. 中途不允许因为想优化系统而偏离写作目标。
12. pipeline 扩容、数据库补丁、审计报告、Web UI、额外工具，全部进入 backlog；除非它们直接阻塞当前章节写作，否则不得打断正文推进。
13. 每一章必须保证上下文连续，写前必须读取上一章尾巴、最近摘要、人物状态、伏笔状态、读者承诺。
14. 每一章 post / ingest 通过后，必须入库，未入库不算章节完成。
15. 每一卷结束后，必须执行 volume_post，生成卷级总结、卷级状态、下一卷承接点并入库。
16. 每一卷必须承接上一卷，卷级上下文未入库，禁止进入下一卷正文。

一句话：

章章入库，卷卷入库。
章章连续，卷卷连续。
post 通过后自动 pre 下一章，不问、不停、不跳卷。

============================================================
二、字数门禁规则 (V5)
============================================================

每章字数按 chapter_type 分级，类型只决定允许上限，不强制下限：

1. 普通正式章：1900～3300 字，最佳 1900～2800 字。

2. 重点章：1900～4200 字，最佳 2200～3300 字。
   重点章不代表必须写多。1900-2800 完成重点内容即可通过。

3. 高潮章 / 卷末章：1900～5500 字，最佳 2300～3800（高潮）/ 2300～4200（卷末）。
   高潮不代表字多。如果 2300 字完成爆点、代价和钩子，不得硬拉长。

4. 授权短章 / 片段：300～1000 字。
   需要 allow_short_chapter=true + short_chapter_reason 非空。

5. 超过类型上限时建议拆章或精简。

核心原则：
- 短而完整，优先通过。长而重复，必须失败。
- 高潮看冲击力，重点看转折力度，卷末看收束和钩子——都不看字数。
- 字数不足时补缺失场景，禁止补水文。

============================================================
三、总卷数与章数建议
============================================================

默认建议：

总卷数：10 卷。
每卷建议章节：25 章。
每卷浮动范围：20 到 29 章。
总章节标准版：250 章左右。
总章节可浮动范围：230 到 290 章。
总字数目标：90 万到 100 万左右。
丰满扩展上限：105 万左右。

原则：

1. 250 章不是硬性死数。
2. 每卷 25 章是建议值，不是固定值。
3. 每卷可以在 20 到 29 章之间浮动。
4. 全书如果写到 260 到 275 章，也可以接受。
5. 不建议低于 230 章，否则中后期容易压缩太狠。
6. 不建议超过 290 章，除非用户明确决定总字数提高到 105 万以上。
7. 卷内主线完成度优先于固定章数。
8. 如果 20 章内无法完成本卷任务，必须扩展。
9. 如果 25 章已经完成本卷任务，不得为了凑到 29 章水文。
10. 如果某卷写到 29 章仍未完成主线，必须做卷内复盘，而不是继续无限拖长。

============================================================
四、卷内节奏模板
============================================================

每卷建议按 5 个阶段推进。

以 25 章标准卷为例：

阶段一：承接与新局面
约 3 到 4 章。
作用：
承接上一卷结尾，交代新地点、新危机、新目标。

阶段二：探索与试错
约 5 到 6 章。
作用：
提出本卷核心问题，进行尝试、失败、误判、代价。

阶段三：冲突升级
约 5 到 6 章。
作用：
对手、制度压力、环境压力、关系压力进入正面冲突。

阶段四：重大失败或重大反转
约 4 到 5 章。
作用：
让主角付出代价，逼迫主角修正方法、理念或关系。

阶段五：卷末爆发与钩子
约 5 到 6 章。
作用：
阶段性解决本卷主线，同时抛出下一卷不可回避的问题。

如果本卷压缩到 20 到 22 章：

1. 阶段一控制在 2 到 3 章。
2. 阶段二控制在 4 到 5 章。
3. 阶段三控制在 4 到 5 章。
4. 阶段四控制在 4 章左右。
5. 阶段五控制在 4 到 5 章。
6. 只保留必要支线，不加新副本。

如果本卷扩展到 27 到 29 章：

1. 优先扩展阶段二和阶段三。
2. 增加失败、反击、关系冲突、人物选择。
3. 不允许只扩展解释设定。
4. 不允许只扩展心理独白。
5. 扩展内容必须推进主线、人物、伏笔、读者承诺之一。

============================================================
五、每章连续执行流程
============================================================

每一章执行：

pre
→ task_card
→ write
→ word_count_gate
→ continuity_gate
→ scene_quality_gate
→ anti_ai_style_gate
→ ingest
→ chapter_ingest_report
→ 自动 pre 下一章

每一卷执行：

本卷第 1 章 pre
→ 本卷第 1 章 write / post / ingest
→ 自动 pre 本卷第 2 章
→ 按章序推进
→ 本卷最后一章 write / post / ingest
→ volume_post
→ volume_summary 入库
→ volume_state 入库
→ next_volume_task_card 生成
→ 自动 pre 下一卷第 1 章

允许暂停的情况只有五种：

1. 用户明确说暂停。
2. 用户明确要求重写或修订。
3. pipeline 出现阻塞，导致不能保证连续性。
4. 章节严重违反字数红线或连续性。
5. 大纲本身出现前后矛盾，必须先修正才能继续。

除此之外，默认继续。

============================================================
六、每章写前必须读取的上下文
============================================================

每一章 write 之前，pre 必须读取并确认以下内容：

1. previous_tail：上一章最后 800 到 1200 字。
2. recent_summaries：最近 3 章摘要。
3. current_volume_goal：当前卷主线目标。
4. current_volume_progress：当前卷已完成进度。
5. previous_chapter_ending_state：上一章结尾状态。
6. previous_chapter_next_hooks：上一章下一章承接点。
7. character_current_states：主要人物当前状态。
8. location_current_states：主要地点当前状态。
9. plot_threads_status：伏笔当前状态。
10. reader_promises_status：读者承诺当前状态。
11. worldbuilding_recent_updates：近期新增世界观。
12. writing_rules：当前生效写作规范。
13. volume_context：上一卷结尾状态和当前卷任务卡。

如果以上任意关键项缺失，allowed_to_write 不得为 true。

禁止出现：

1. 只看大纲写下一章。
2. 只看上一章标题写下一章。
3. 不读上一章结尾写下一章。
4. 不查人物状态写人物关系变化。
5. 不查伏笔和读者承诺就开新坑。
6. 不查当前卷进度就随意加副本。

============================================================
七、每章必须入库的内容
============================================================

每章 post / ingest 通过后，必须入库以下内容：

1. chapters：章节正文。
2. chapter_versions：章节版本。
3. chapter_chunks：章节切片。
4. chapter_summaries：章节摘要。
5. character_state_updates：人物状态变化。
6. worldbuilding_updates：世界观新增或修正。
7. plot_threads：伏笔新增、推进、兑现、延迟。
8. reader_promises：读者承诺新增、推进、兑现、延迟。
9. next_chapter_hooks：下一章必须承接点。
10. location_state_updates：地点和重要物件状态变化。
11. timeline_events：关键时间线事件。
12. novel_logs：写作日志。
13. fts_refresh_status：FTS / 检索索引刷新状态。

每章必须生成 chapter_ingest_report，至少包含：

1. 章节编号。
2. 章节标题。
3. 实际字数。
4. 是否通过字数门禁。
5. 是否通过连续性门禁。
6. 是否通过场景质量门禁。
7. 是否通过反 AI 腔门禁。
8. 是否完成入库。
9. 新增或推进了哪些伏笔。
10. 新增或推进了哪些读者承诺。
11. 下一章必须承接什么。

如果 ingest 失败：

章节视为未完成。
禁止 pre 下一章。
禁止写下一章。
必须先修复 ingest。

============================================================
八、每卷必须执行 volume_post
============================================================

每一卷最后一章 post / ingest 通过后，不能直接跳下一卷正文。
必须先执行 volume_post。

volume_post 必须生成并入库：

1. volume_summary：本卷 1000 到 2000 字总结。
2. volume_opening_state：本卷开局状态。
3. volume_ending_state：本卷结尾状态。
4. volume_main_arc：本卷主线完成情况。
5. volume_character_arcs：主要人物阶段变化。
6. volume_worldbuilding_updates：本卷新增世界观。
7. volume_plot_threads_status：本卷伏笔新增、推进、兑现、遗留。
8. volume_reader_promises_status：本卷读者承诺兑现情况。
9. unresolved_hooks：下一卷必须承接的坑。
10. next_volume_task_card：下一卷任务卡。
11. next_volume_opening_requirements：下一卷第 1 章开头必须承接的细节。
12. volume_quality_review：本卷节奏、爽点、拖沓、AI 腔、设定密度复盘。

volume_post 失败：

当前卷视为未完成。
禁止 pre 下一卷第 1 章。
禁止写下一卷正文。
必须先修复 volume_post。

============================================================
九、全书标题骨架与大纲入库规则
============================================================

正式连续写正文之前，必须先把整本书的“标题骨架 + 卷级大纲 + 章节级简纲”入库，避免后续写作跑偏、跳卷、乱加副本、忘记卷目标。

全书标题骨架不是只有卷名和章名。
它必须同时包含：

1. 全书总大纲。
2. 卷名。
3. 每卷核心任务。
4. 每卷卷末必须完成事项。
5. 每卷建议章数与浮动范围。
6. 每章临时章名。
7. 每章一句话目标。
8. 每章必须推进的主线、人物、伏笔或读者承诺。
9. 每章结尾钩子方向。
10. 后续可修改的标题状态记录。

一句话：

卷名要先定。
章名可以临时。
大纲必须入库。
章节目标不能空。

------------------------------------------------------------
1. 开写正文前必须先完成标题骨架入库
------------------------------------------------------------

正式连续写正文前，必须先生成并入库全书标题骨架。

标题骨架至少包括：

1. novel_outline：全书总大纲。
2. volume_plans：卷名、卷目标、卷末必须完成事项。
3. chapter_plans：每章临时章名、章节目标、必须推进内容、结尾钩子方向。
4. title_history：后续改名记录。
5. outline_version：当前大纲版本号。
6. plan_status：planned / active / revised / deprecated。

如果标题骨架没有入库：

1. 禁止开始长期连续写作。
2. 禁止直接从某一卷中途乱写。
3. 禁止只靠聊天记忆推进全书。
4. 禁止只看卷名写正文。
5. 禁止只看章名写正文。

------------------------------------------------------------
2. 卷名规则
------------------------------------------------------------

卷名需要相对稳定。

卷名入库字段建议：

1. volume_no：卷序号。
2. planned_title：预设卷名。
3. final_title：最终卷名。
4. title_status：planned / revised / final。
5. suggested_chapters：建议章数，默认 25。
6. min_chapters：最低章数，默认 20。
7. max_chapters：最高章数，默认 29。
8. volume_goal：本卷核心任务。
9. opening_state：本卷开局状态。
10. ending_target：本卷卷末目标。
11. must_complete：本卷必须完成事项。
12. unresolved_hooks_to_next：本卷将遗留给下一卷的钩子方向。

规则：

1. 卷名开写前必须入库。
2. 卷名可以后续修改，但不能随意修改。
3. 卷名修改必须记录原因。
4. 卷名修改不能改变卷序。
5. 卷名修改不能导致本卷核心任务漂移。
6. 卷名最终确认应放在 volume_post 或用户明确确认之后。

------------------------------------------------------------
3. 章名规则
------------------------------------------------------------

章名可以先粗，不要求一次性完美。

章名本质是写作导航，不是死标题。

每章必须区分：

1. planned_title：预设章名。
2. final_title：正式章名。
3. title_status：planned / revised / final。
4. title_change_reason：改名原因。

规则：

1. 每章必须有 planned_title，但可以是临时标题。
2. 每章必须有 chapter_goal，不能只有章名。
3. 正文写作时，以 chapter_goal 和 chapter_task_card 为准，不得只看章名写正文。
4. 如果正文重点和 planned_title 不一致，优先修改章名，不要强行改正文去贴章名。
5. 改章名不能改变章节编号。
6. 改章名必须写入 title_history。
7. 每章 post / ingest 时，必须检查 final_title 是否贴合正文。

------------------------------------------------------------
4. 章节级简纲规则
------------------------------------------------------------

每章入库时，不能只存标题。

每章必须有 chapter_brief。

chapter_brief 至少包含：

1. chapter_no：章节编号。
2. volume_no：所属卷数。
3. planned_title：预设章名。
4. chapter_goal：本章一句话目标。
5. main_event：本章主要事件。
6. character_focus：本章重点人物。
7. conflict_point：本章冲突点。
8. must_include：本章必须包含的内容。
9. plot_threads_to_advance：本章推进的伏笔。
10. reader_promises_to_advance：本章推进的读者承诺。
11. ending_hook_direction：本章结尾钩子方向。
12. continuity_from_previous：必须承接上一章的内容。

最低要求：

1. chapter_goal 不能为空。
2. main_event 不能为空。
3. conflict_point 不能为空。
4. ending_hook_direction 不能为空。
5. continuity_from_previous 不能为空，第一章除外。

如果章节级简纲为空：

1. 禁止生成 chapter_task_card。
2. 禁止 write 正文。
3. 禁止只靠大纲摘要临时发挥。

------------------------------------------------------------
5. 标题骨架与正文写作的关系
------------------------------------------------------------

标题骨架是导航，不是镣铐。

执行原则：

1. 标题骨架负责控制方向。
2. chapter_task_card 负责控制本章执行。
3. 正文实际效果优先于预设章名。
4. 正文不能背离卷级任务。
5. 正文不能背离全书主线。
6. 正文可以让章名后续调整。
7. 正文不能让章节编号混乱。
8. 正文不能因为章名临时变化而跳卷、跳章。

优先级排序：

全书主题 > 卷级目标 > 章节目标 > 正文效果 > 章名美观。

============================================================
十、建议数据库表
============================================================

建议新增 volume_plans 表：

CREATE TABLE IF NOT EXISTS volume_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL,
    volume_no INTEGER NOT NULL,
    planned_title TEXT NOT NULL,
    final_title TEXT DEFAULT '',
    title_status TEXT DEFAULT 'planned',
    suggested_chapters INTEGER DEFAULT 25,
    min_chapters INTEGER DEFAULT 20,
    max_chapters INTEGER DEFAULT 29,
    volume_goal TEXT DEFAULT '',
    opening_state TEXT DEFAULT '',
    ending_target TEXT DEFAULT '',
    must_complete TEXT DEFAULT '',
    unresolved_hooks_to_next TEXT DEFAULT '',
    outline_version TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

建议新增 chapter_plans 表：

CREATE TABLE IF NOT EXISTS chapter_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL,
    volume_no INTEGER NOT NULL,
    chapter_no INTEGER NOT NULL,
    planned_title TEXT NOT NULL,
    final_title TEXT DEFAULT '',
    title_status TEXT DEFAULT 'planned',
    chapter_goal TEXT NOT NULL,
    main_event TEXT DEFAULT '',
    character_focus TEXT DEFAULT '',
    conflict_point TEXT DEFAULT '',
    must_include TEXT DEFAULT '',
    plot_threads_to_advance TEXT DEFAULT '',
    reader_promises_to_advance TEXT DEFAULT '',
    ending_hook_direction TEXT DEFAULT '',
    continuity_from_previous TEXT DEFAULT '',
    title_change_reason TEXT DEFAULT '',
    outline_version TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

建议新增 title_history 表：

CREATE TABLE IF NOT EXISTS title_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL,
    volume_no INTEGER,
    chapter_no INTEGER,
    old_title TEXT DEFAULT '',
    new_title TEXT NOT NULL,
    title_type TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

============================================================
十一、当前执行任务：先做全书标题骨架入库
============================================================

当前不是写正文。
当前不是扩容 pipeline。
当前不是做审计报告。
当前不是补 Web UI。
当前不是重新设计数据库系统。

当前唯一任务：

生成并准备入库当前小说项目的全书标题骨架。

必须生成：

1. novel_outline。
2. volume_plans。
3. chapter_plans。
4. 每章 planned_title。
5. 每章 chapter_goal。
6. 每章 main_event。
7. 每章 character_focus。
8. 每章 conflict_point。
9. 每章 must_include。
10. 每章 plot_threads_to_advance。
11. 每章 reader_promises_to_advance。
12. 每章 ending_hook_direction。
13. 每章 continuity_from_previous。

禁止：

1. 不许写正文。
2. 不许问继续吗。
3. 不许扩容 pipeline。
4. 不许做 Web UI。
5. 不许用审计报告代替标题骨架。
6. 不许只生成卷名章名。
7. 不许没有 chapter_goal。
8. 不许没有 conflict_point。
9. 不许没有 ending_hook_direction。
10. 不许因为数据库表暂缺而停止生成骨架。

如果数据库表已存在，直接入库。
如果数据库表不存在，输出 SQL 建表语句和可导入结构化文件。
系统缺口进入 backlog，不阻塞标题骨架生成。

标题骨架完成后停止。
不要写正文。
等待用户下一步指令。

============================================================
十二、Skill 执行输入
============================================================

执行本 Skill 时，用户或上游系统应提供：

1. novel_title：小说名。
2. novel_slug：小说项目标识。
3. genre：类型。
4. target_word_count：目标总字数。
5. target_volumes：目标卷数。
6. target_chapters：目标章节数。
7. current_chapter_no：当前章节号。
8. current_volume_no：当前卷号。
9. outline_path：大纲路径。
10. db_path：数据库路径。
11. writing_rules_path：写作规范路径。
12. user_current_command：用户当前指令。

如果部分输入缺失：

1. 不得编造数据库路径。
2. 不得跳过上下文检查。
3. 可以输出“缺失项列表”。
4. 如果不影响当前标题骨架生成，可以继续生成骨架。
5. 如果影响正文连续性，则禁止 write 正文。

============================================================
十三、Skill 输出
============================================================

根据任务不同，输出以下内容之一：

1. 标题骨架文件。
2. volume_plans 入库结果。
3. chapter_plans 入库结果。
4. chapter_task_card。
5. 正文章节。
6. chapter_ingest_report。
7. volume_post_report。
8. backlog 列表。
9. 阻塞原因报告。

输出必须明确：

1. 当前执行了哪一步。
2. 是否写正文。
3. 是否入库。
4. 是否允许进入下一章。
5. 是否允许进入下一卷。
6. 如果不允许，阻塞原因是什么。

============================================================
十四、最终执行句
============================================================

从现在开始，执行本 Skill 时必须遵守：

本小说按用户指定卷数与章节规划执行；默认建议 10 卷、250 章左右，每卷建议 25 章，浮动 20 到 29 章。
正式连续写作前，必须先完成全书标题骨架入库；标题骨架必须包含全书总大纲、卷级大纲、章节级简纲、临时章名和章节目标。
每章字数按 chapter_type 分级：普通1900-3300, 重点1900-4200, 高潮1900-5500。
每一卷都必须按顺序写完。
当前卷未完成，禁止跳卷。
每章必须承接上一章。
每卷必须承接上一卷。
每章完成后必须 ingest 入库，未入库不算完成。
每卷完成后必须 volume_post 入库，未入库不算完成。
当前章 post / ingest 通过后，立刻 pre 下一章。
当前卷最后一章 post / ingest / volume_post 通过后，立刻 pre 下一卷第一章。
不问“继续吗”，不问“要不要修整”，不因为扩容 pipeline、补数据库、做审计报告偏离正文写作。
除非用户明确暂停、重写、修订，否则默认按章序、卷序无缝推进。

============================================================
十五、执行证据原则
============================================================

以下原则不是口号，每一条都必须有对应的证据文件：

1. **章连续性不是口号** — 每章必须产出 `continuity_evidence_report.json`，证明本章开头从上一章结尾自然承接。
2. **卷连续性不是口号** — 每卷必须产出 `volume_bridge_report.json`，证明本卷从上一卷结尾自然承接。
3. **写作不是水文** — 每个 scene 必须提交 `scene_delta_report.json`，证明场景有实质推进而非 padding。
4. **新事实不是自由创作** — 每个 hard fact 必须提交证据来源（task_card / plan / state / user_instruction），写入 `canon_evidence_map.json`。
5. **Hermes 不得用自然语言声称执行** — 必须提供 `execution_receipt.json`，包含 commands_run、exit_codes、timestamps，证明工具确实调用过。
