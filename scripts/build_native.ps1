param(
  [ValidateSet('windows','linux','macos')][string]$Target = 'windows',
  [switch]$SkipSign
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "artifacts/native/$Target"
New-Item -ItemType Directory -Force $out | Out-Null
$sha = (git -C $root rev-parse HEAD 2>$null); if (-not $sha) { $sha = 'unknown' }
$env:PYTHONPATH = $root
$env:PROSEFORGE_NATIVE_OUT = $out
$env:PROSEFORGE_NATIVE_SHA = $sha
$env:PROSEFORGE_NATIVE_TARGET = $Target
python -c "from packaging.manifest import build_manifest,write_manifest; import os; write_manifest(os.path.join(os.environ['PROSEFORGE_NATIVE_OUT'],'manifest.json'), build_manifest(git_sha=os.environ['PROSEFORGE_NATIVE_SHA'], target_os=os.environ['PROSEFORGE_NATIVE_TARGET']))"
"native bundle placeholder: $Target`nsigning skipped=$SkipSign" | Set-Content (Join-Path $out 'BUILD.txt')
Write-Output $out
