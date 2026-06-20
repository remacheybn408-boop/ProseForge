---
name: nf-project
description: Manage ProseForge workspace, slots, outlines, and exports. Use when the user asks to initialize the workspace, create a novel slot, list slots, inspect workspace status, manage outlines, or export a novel.
---

# nf_project

Use this skill when the user wants Claude Code to manage the local ProseForge
workspace and the task maps to one of these actions:

- `init`
- `create`
- `list`
- `status`
- `outline`
- `export`

This plugin does not expose MCP tools. Instead, call the **shared wrapper
script** that ships with the Codex plugin:

```powershell
python plugin/proseforge-codex/scripts/nf_project.py --action <action> ...
```

Always invoke from the repo root (`D:\ProseForge`).

## Action mapping

- `init`: initialize the local `workspace/`.
- `create`: create a slot with a title.
- `list`: list registered slots.
- `status`: inspect the active slot and registry state.
- `outline`: `add`, `list`, or `switch` outlines (via `--sub-action`).
- `export`: export a novel as `txt` or `md`.

## Required arguments

| action  | required |
|---------|----------|
| `create` | `--slot-name --title` |
| `outline --sub-action add` | `--file-path` |
| `outline --sub-action switch` | `--outline-id` |

## Optional arguments

- `--slug` for `export`
- `--format txt|md` for `export`
- `--output <path>` for `export`

## Examples

```powershell
python plugin/proseforge-codex/scripts/nf_project.py --action init
python plugin/proseforge-codex/scripts/nf_project.py --action create --slot-name gwdz --title "诡雾灯盏"
python plugin/proseforge-codex/scripts/nf_project.py --action outline --sub-action add --file-path examples/demo_novel/outline_skeleton.json
python plugin/proseforge-codex/scripts/nf_project.py --action export --slug demo_novel --format txt
```

## Discipline

- Prefer these two wrapper scripts over ad hoc shell commands so the
  Claude-side workflow stays aligned with the Hermes and Codex surfaces.
- `nf_project init` must be run once before any `nf_pipeline` action that
  touches a slot.
- No outline → no writing: `nf_project outline add` is a precondition for
  `nf_pipeline pre`.
