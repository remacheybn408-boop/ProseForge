---
name: nf-pipeline
description: Run the ProseForge writing pipeline for chapter and volume workflows. Use when the user asks to prepare a chapter, run write-after gates, do multi-agent review, batch-process chapters, or build a volume summary.
---

# nf_pipeline

Use this skill when the user wants Claude Code to drive the ProseForge
writing pipeline and the task maps to one of these actions:

- `pre`
- `post`
- `review`
- `batch`
- `volume`

This plugin does not expose MCP tools. Instead, call the **shared wrapper
script** that ships with the Codex plugin (the Claude and Codex plugins
deliberately reuse the same scripts so all surfaces stay in sync):

```powershell
python plugin/proseforge-codex/scripts/nf_pipeline.py --action <action> ...
```

Always invoke from the repo root (`D:\ProseForge`) so the wrapper can resolve
`src/` imports correctly.

## Action mapping

- `pre`: prepare chapter context before writing (task card + context pack + pipeline state).
- `post`: run post-write processing — word-count gate, Guard registry, human texture, ingest.
- `review`: run the 6-agent review flow (`light` or `full` mode).
- `batch`: run `post` for a chapter range `from-ch..to-ch`.
- `volume`: build the volume-level summary + bridge report.

## Required arguments

| action   | required |
|----------|----------|
| `pre`    | `--slug --title --vol-no --chapter-no` |
| `post`   | `--slug --title --vol-no --chapter-no` |
| `review` | `--slug --vol-no --chapter-no` |
| `batch`  | `--slug --title --vol-no --from-ch --to-ch` |
| `volume` | `--slug --title --vol-no` |

## Optional arguments

- `--chapter-type normal|key|climax`
- `--mode light|full` for `review`
- `--project-root <path>` and `--config-path <path>` when the default repo/config location is not correct

## Examples

```powershell
python plugin/proseforge-codex/scripts/nf_pipeline.py --action pre --slug demo_novel --title "Demo Novel" --vol-no 1 --chapter-no 3
python plugin/proseforge-codex/scripts/nf_pipeline.py --action review --slug demo_novel --vol-no 1 --chapter-no 3 --mode full
python plugin/proseforge-codex/scripts/nf_pipeline.py --action batch --slug demo_novel --title "Demo Novel" --vol-no 1 --from-ch 1 --to-ch 5
```

## Output handling

The wrapper prints the result as JSON on stdout. Summarize the JSON back to the
user in a few sentences (status, key counts, any error). Do not paste raw
multi-screen JSON unless the user explicitly asks for it. Exit code is non-zero
when `status == "error"`; surface that clearly when it happens.
