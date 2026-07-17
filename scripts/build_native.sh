#!/usr/bin/env bash
set -euo pipefail
target="linux"
format="tar.gz"
skip_sign=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) target="$2"; shift 2;;
    --format) format="$2"; shift 2;;
    --skip-sign) skip_sign=1; shift;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="$root/artifacts/native/$target"
mkdir -p "$out"
git_sha="$(git -C "$root" rev-parse HEAD 2>/dev/null || echo unknown)"
OUT="$out" SHA="$git_sha" TARGET="$target" PYTHONPATH="$root" python -c 'from packaging.manifest import build_manifest,write_manifest; import os; write_manifest(os.environ["OUT"]+"/manifest.json", build_manifest(git_sha=os.environ["SHA"], target_os=os.environ["TARGET"]))'
printf 'native bundle placeholder: %s (%s)\n' "$target" "$format" > "$out/BUILD.txt"
printf 'signing skipped=%s\n' "$skip_sign" >> "$out/BUILD.txt"
echo "$out"
