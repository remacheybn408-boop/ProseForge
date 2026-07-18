# Register the ProseForge logon task (start "proseforge web" at user logon).
# Called by the Inno Setup installer when the "autostart" task is selected,
# or manually:  powershell -ExecutionPolicy Bypass -File service_install.ps1
[CmdletBinding()]
param(
    [string]$Executable = "$env:ProgramFiles\ProseForge\proseforge.exe",
    [string]$DataDir = "$env:LOCALAPPDATA\ProseForge",
    [string]$TaskName = 'ProseForge'
)

$ErrorActionPreference = 'Stop'

Write-Output "[1/4] Checking executable: $Executable"
if (-not (Test-Path -LiteralPath $Executable)) {
    Write-Error "Executable not found: $Executable"
    exit 1
}

Write-Output "[2/4] Ensuring per-user data directory: $DataDir"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

Write-Output "[3/4] Removing any existing scheduled task '$TaskName'"
& schtasks.exe /End /TN $TaskName 2>$null | Out-Null
& schtasks.exe /Delete /TN $TaskName /F 2>$null | Out-Null

# /TR value: quoted exe path + arguments. \" survives PowerShell's native
# argument marshaling and is unescaped by schtasks/CRT as a literal quote.
$taskRun = '\"' + $Executable + '\" web --data-dir \"' + $DataDir + '\"'
Write-Output "[4/4] Registering scheduled task '$TaskName' (ONLOGON): $taskRun"
& schtasks.exe /Create /TN $TaskName /SC ONLOGON /TR $taskRun /F | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "schtasks /Create failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Output "Done. '$TaskName' will start 'proseforge web' at next logon; data dir: $DataDir"
exit 0
