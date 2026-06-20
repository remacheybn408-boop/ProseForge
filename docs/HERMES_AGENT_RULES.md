# Hermes Agent 正文写作强制规则

本项目的 8 步流水线不是普通提示词，而是 Agent 强制执行协议。

当用户要求写正文、续写、写第 N 章、下一章、写完本卷、继续整本书时，Hermes Agent 必须进入 NOVEL_WRITE_MODE，并调用 novel-factory skill。

禁止使用普通聊天模式直接生成章节正文。

正文写作前必须输出执行头：

```
mode = NOVEL_WRITE_MODE
required_skill = novel-factory
skill_called = true
pipeline = pre → task_card → scene_plan → write_chunks → assemble_chapter → word_count → continuity → hallucination → scene → anti_ai → padding → voice_guards → qgp → editor_revision → concrete_anchor → scene_causality → dialogue_naturalness → style_variation → compliance_selfcheck → final_submission → ingest
```

如果 novel-factory skill 不可用，必须停止并报错：

```
ERROR: novel-factory skill not available.
Refuse to write novel正文 in normal chat mode.
```

## 硬规则

- **No commands_run** = 未执行
- **No run_report** = 章节未完成
- **No PASS_NOVEL_WRITE_GUARD** = 未通过
- **No ingest_done** = 未入库
- **No previous_tail_used** = 上下文不连续
- **No volume_bridge_report** = 卷不连续
- **No execution_receipt** = 执行未证明

详见 [novel-factory Router Skill](skills/novel_factory_router_SKILL.md)
