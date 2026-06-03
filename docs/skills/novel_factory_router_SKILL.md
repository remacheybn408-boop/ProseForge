# novel-factory Router Skill

版本：V1.0

用途：
强制 Hermes Agent 在长篇小说正文写作任务中调用 novel-factory skill，禁止普通聊天模式直接写正文。

============================================================
一、最高优先级
============================================================

当用户要求写正文、续写、继续写、写第 N 章、下一章、写完本卷、继续整本书时，必须进入 NOVEL_WRITE_MODE。

NOVEL_WRITE_MODE 下必须调用 novel-factory skill。

如果 novel-factory skill 不可用，必须停止并报错，禁止普通聊天模式代写正文。

错误格式：

ERROR: novel-factory skill not available.
Refuse to write novel正文 in normal chat mode.

============================================================
二、模式路由
============================================================

PLAN_MODE 触发词：

- 生成标题骨架
- 做全书大纲
- 做卷级大纲
- 做章节规划
- 生成 chapter_plans
- 生成 volume_plans
- 入库标题骨架
- 补大纲
- 做设定表

NOVEL_WRITE_MODE 触发词：

- 写第 N 章
- 续写
- 继续写
- 下一章
- 写正文
- 写完本卷
- 继续整本书
- 从上一章继续
- 根据 task_card 写
- 按 pipeline 写
- 生成本章正文

当 PLAN_MODE 和 NOVEL_WRITE_MODE 同时出现时：

1. 如果用户主要目标是"正文"，优先 NOVEL_WRITE_MODE。
2. 如果用户明确说"不要写正文，只做骨架"，才进入 PLAN_MODE。
3. "标题骨架未完成"只能阻止长期连续写作，不能阻止用户明确要求的单章试写；但必须在报告中提示风险。

============================================================
三、正文模式执行头
============================================================

每次进入 NOVEL_WRITE_MODE，Agent 必须先输出执行头：

mode = NOVEL_WRITE_MODE
required_skill = novel-factory
skill_called = true
pipeline = pre → task_card → scene_plan → write_chunks → assemble_chapter → word_count → continuity → hallucination → scene → anti_ai → padding → ingest

如果无法确认 skill_called=true，禁止输出正文。

============================================================
四、正文模式硬流程
============================================================

NOVEL_WRITE_MODE 必须执行：

1. pre
2. 读取上一章尾巴
3. 读取最近摘要
4. 读取人物状态
5. 读取伏笔状态
6. 读取读者承诺
7. 生成 chapter_task_card
8. scene_plan（场景规划）
9. write_chunks（分段写作；普通正式章按 scene_budget_plan.json / 固定模板控制 chunk 字数；300～1000 只用于用户授权短章、片段、微场景或样章）
10. assemble_chapter
11. chapter_word_count_gate（只检查 assembled_chapter）
12. continuity_gate
13. hallucination_gate
14. scene_quality_gate
15. anti_ai_style_gate
16. padding_guard
17. ingest
18. chapter_ingest_report
19. 自动 pre 下一章

禁止：

1. 没 pre 就写正文。
2. 没 task_card 就写正文。
3. 没调用 novel-factory 就写正文。
4. 没 ingest 就说章节完成。
5. 低于类型最低线还入正稿。
6. 用户要求写正文时转去做审计。
7. 用户要求写正文时转去扩容系统。
8. 问"要不要继续"。
9. 跳卷、跳章。
10. 当前章未入库就写下一章。

### 证据门禁约束

11. 非首章写作：必须读取 previous_tail **且** 生成 continuity_evidence_report。
12. 任何新 hard fact：必须可追溯到 task_card / plan / state / user_instruction（写入 canon_evidence_map）。
13. 每个 scene：必须提交 scene_delta，证明该场景推进了主线/人物/伏笔/承诺/世界观/情绪之一。
14. 章节未通过 continuity_evidence / canon_evidence / padding_evidence 任一证据门禁：**禁止 ingest**。
15. 章节没有 execution_receipt：**不得声称已执行**。

============================================================
五、失败判定
============================================================

出现以下任意情况，判定本次任务失败：

1. mode 不是 NOVEL_WRITE_MODE，却输出了正文。
2. required_skill 不是 novel-factory，却输出了正文。
3. skill_called 不是 true，却输出了正文。
4. 缺少 pre。
5. 缺少 chapter_task_card。
6. 缺少 word_count_gate。
7. 缺少 ingest。
8. 字数低于类型最低线，未被用户明确允许短章。
9. 没有 chapter_ingest_report。
10. 用户要求写正文，Agent 输出规划、审计、解释、扩容建议。

失败时必须输出：

FAILED_NOVEL_WRITE_GUARD

并说明失败原因。

============================================================
六、标题骨架规则修正
============================================================

long_novel_writing_SKILL 中"当前唯一任务是标题骨架"只在用户明确要求标题骨架时生效。

当用户明确要求写正文时：

1. 如果标题骨架已入库：正常进入 NOVEL_WRITE_MODE。
2. 如果标题骨架未入库：允许输出阻塞报告，或者只写用户明确要求的单章试写；但不得假装完成长期连续写作。
3. 不得用"标题骨架任务"无限阻止正文写作。
4. 不得用"系统缺口"代替用户要求的正文任务。

============================================================
七、输出报告
============================================================

每次正文任务结束后，必须输出：

chapter_run_report:
  mode: NOVEL_WRITE_MODE
  required_skill: novel-factory
  skill_called: true
  chapter_no:
  title:
  word_count:
  word_count_gate:
  continuity_gate:
  scene_quality_gate:
  anti_ai_style_gate:
  ingest_done:
  next_allowed:
  next_action:

如果 ingest_done=false：

next_allowed=false
next_action=repair_current_chapter

如果 ingest_done=true：

next_allowed=true
next_action=pre_next_chapter
