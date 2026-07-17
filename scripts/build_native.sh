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
if [[ "$format" == "zip" ]]; then
  archive_format=zip
else
  archive_format=tar.gz
fi
PYTHONPATH="$root" python -m packaging.native_bundle \
  --root "$root" --output "$out" --target "$target" --format "$archive_format"
