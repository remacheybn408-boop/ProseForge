[Setup]
AppName=ProseForge
AppVersion=1.5.0
DefaultDirName={autopf}\ProseForge
Uninstallable=yes
[Files]
Source: "artifacts\native\windows\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\ProseForge\logs"
