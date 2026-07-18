# Stop and remove the ProseForge logon task.
# This script never touches user data: everything under
# %LOCALAPPDATA%\ProseForge (database, backups, logs) is preserved.
[CmdletBinding()]
param([string]$TaskName = 'ProseForge')

Write-Output "Stopping scheduled task '$TaskName' (no-op if not running)..."
& schtasks.exe /End /TN $TaskName 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Output "  task was not running." }

Write-Output "Deleting scheduled task '$TaskName' (no-op if absent)..."
& schtasks.exe /Delete /TN $TaskName /F 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Output "  task did not exist." }

Write-Output "Autostart removed. User data is preserved at $env:LOCALAPPDATA\ProseForge"
exit 0
