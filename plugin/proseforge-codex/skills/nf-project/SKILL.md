---
name: nf-project
description: Run the local Novel Forge project wrapper for workspace, slot, outline, and export workflows without MCP.
---

# nf_project

Use this skill when the user wants Codex to manage the local Novel Forge
workspace and the task maps to one of these actions:

- `init`
- `create`
- `list`
- `status`
- `outline`
- `export`

This plugin does not expose MCP tools. Instead, call the local wrapper script:

```powershell
python plugin/hermes-forgen-codex/scripts/nf_project.py --action <action> ...
```

## Action mapping

- `init`: initialize the local `workspace/`.
- `create`: create a slot with a title.
- `list`: list registered slots.
- `status`: inspect the active slot and registry state.
- `outline`: `add`, `list`, or `switch` outlines.
- `export`: export a novel as `txt` or `md`.

## Required arguments

- `create`: `--slot-name --title`
- `outline --sub-action add`: `--file-path`
- `outline --sub-action switch`: `--outline-id`

## Optional arguments

- `--slug` for `export`
- `--format txt|md` for `export`
- `--output <path>` for `export`

## Examples

```powershell
python plugin/hermes-forgen-codex/scripts/nf_project.py --action init
python plugin/hermes-forgen-codex/scripts/nf_project.py --action create --slot-name gwdz --title "诡雾灯盏"
python plugin/hermes-forgen-codex/scripts/nf_project.py --action outline --sub-action add --file-path examples/demo_novel/outline_skeleton.json
python plugin/hermes-forgen-codex/scripts/nf_project.py --action export --slug demo_novel --format txt
```

Prefer these two wrapper scripts over ad hoc shell commands so the Codex-side
workflow stays aligned with the plugin surface.
