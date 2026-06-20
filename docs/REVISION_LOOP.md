# Revision Loop — 自动改稿闭环 v0.4.0

## 1. 什么是 Revision Loop

Revision Loop 是 v0.4.0 的自动改稿闭环系统。它把门禁检查发现的问题转换成可执行的修改任务，在 controlled 模式下生成可审阅的改稿草案。

```
门禁检查 → 合并问题 → Top 修改任务 → 规划补丁 → 生成改稿 → 复查门禁 → 对比报告
```

## 2. 为什么不自动覆盖原文

自动改稿不等于自动洗稿。Revision Loop 遵循以下原则：

- **不覆盖原文**: 始终输出 `.revised.txt`，原文不动
- **不自动入库**: 改稿不会自动写入数据库
- **不整章洗稿**: 默认只改问题段落
- **不追求 WARNING 清零**: 只修 Top 3-5 个高置信度问题
- **不改风格**: 保留方言、文言、角色口癖、伏笔和结尾钩子

## 3. 三种模式

### suggest 模式

只生成 `revision_tasks.json`，不改文。适合想自己改稿的场景。

```bash
python scripts/revision_loop_controller.py \
  --input chapter.txt --report final_report.json \
  --mode suggest --out-dir reports/revision_loop
```

### controlled 模式（默认推荐）

完整闭环：生成任务 → 规划补丁 → 生成改稿草案 → 复查门禁 → 对比报告。

```bash
python scripts/revision_loop_controller.py \
  --input chapter.txt --report final_report.json \
  --mode controlled --max-rounds 2 \
  --out-dir reports/revision_loop
```

### aggressive 模式（默认关闭）

需要在 config 中显式启用 `allow_aggressive_mode: true`。

## 4. 改稿草案和原文的区别

| 文件 | 说明 |
|------|------|
| `chapter_003.txt` | 原文，不动 |
| `chapter_003.revised.txt` | 改稿草案，只改了问题段落 |
| `chapter_003.rewrite_log.json` | 改动记录 |
| `chapter_003.revision_diff_report.json` | 改前/改后对比 |

## 5. 如何阅读 diff report

`revision_diff_report.json` 关键字段：

- `summary.changed_paragraphs`: 被修改的段落数
- `summary.unchanged_ratio`: 未改动比例（越高越好）
- `task_results`: 每个修改任务的执行状态
- `risk_flags`: 改动风险提示
- `recommendation`: `REVIEW_BEFORE_ACCEPT` / `REVIEW_CAREFULLY` / `REVISION_REJECTED`

## 6. 什么情况下标记 REVISION_REJECTED

- 改动比例超过 35%
- 改稿后合规风险升高
- 对白段落显著丢失
- 连续性变差
- 角色口吻丢失

## 7. 为什么不追求 WARNING 清零

- 方言、文言、角色口癖等"异常"是小说合法艺术手段
- 短章节、过渡章天然会触发某些门禁
- 过度修改会破坏作者风格
- 门禁是审稿助手，不是考试判卷

## 8. 如何手动采用 revised draft

1. 阅读 `revision_diff_report.json` 确认改动合理
2. 对比 `chapter.txt` 和 `chapter.revised.txt`
3. 如果采纳：手动替换原文件
4. 运行 `chapter_pipeline.py post` 入库

## 9. 如何关闭 Revision Loop

在 `config.json` 中：

```json
{
  "revision_loop": {
    "enabled": false
  }
}
```

## 10. 如何只生成任务

```bash
python scripts/revision_task_generator.py \
  --input chapter.txt \
  --report final_submission_report.json \
  --out revision_tasks.json
```
