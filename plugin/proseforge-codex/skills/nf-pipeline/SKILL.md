---
name: nf-pipeline
description: Run the local Novel Forge pipeline wrapper for chapter and volume workflows without MCP.
---

# nf_pipeline

Use this skill when the user wants to run the Novel Forge writing pipeline from
Codex and the task maps to one of these actions:

- `pre`
- `post`
- `review`
- `batch`
- `volume`
- `rewrite`
- `accept`

This plugin does not expose MCP tools. Instead, call the local wrapper script:

```powershell
python plugin/proseforge-codex/scripts/nf_pipeline.py --action <action> ...
```

## Action mapping

- `pre`: prepare chapter context before writing.
- `post`: run post-write processing for a chapter.
- `review`: run the multi-agent review flow.
- `batch`: run `post` for a chapter range.
- `volume`: build the volume-level summary.
- `rewrite`: 读 post 去重报告，产「改写卡」(outputs/rewrite_cards/) + revision_tasks.json，由 Agent 改写并写 chapter_NNN_revised.txt。内核不调 LLM。
- `accept`: 原稿 vs revised 出 diff + recommendation；加 `--ingest` 审核通过则入库（追加快照，不覆盖）。

## Required arguments

- `pre`: `--slug --title --vol-no --chapter-no`
- `post`: `--slug --title --vol-no --chapter-no`
- `review`: `--slug --vol-no --chapter-no`
- `batch`: `--slug --title --vol-no --from-ch --to-ch`
- `volume`: `--slug --title --vol-no`
- `rewrite`: `--slug --title --vol-no --chapter-no`
- `accept`: `--slug --title --vol-no --chapter-no` (`--ingest` 可选)

## Optional arguments

- `--chapter-type normal|key|climax`
- `--mode light|full` for `review` — light 跑 3 个 agent（continuity/prose/plot），full 跑 6 个（额外加 character/reader/detail）；两者审稿阈值相同，区别只在覆盖范围
- `--project-root <path>` and `--config-path <path>` when the repo/config is not the default location

## Examples

```powershell
python plugin/proseforge-codex/scripts/nf_pipeline.py --action pre --slug demo_novel --title "Demo Novel" --vol-no 1 --chapter-no 3
python plugin/proseforge-codex/scripts/nf_pipeline.py --action review --slug demo_novel --vol-no 1 --chapter-no 3 --mode full
python plugin/proseforge-codex/scripts/nf_pipeline.py --action batch --slug demo_novel --title "Demo Novel" --vol-no 1 --from-ch 1 --to-ch 5
```

Print the returned JSON back to the user in summarized form instead of pasting
raw command output unless the user explicitly asks for it.
