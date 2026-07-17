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
python -m packaging.native_bundle --root $root --output $out --target $Target --format zip
Write-Output $out
