; Inno Setup installer script for QEMU-MCP
; Compile:  iscc scripts/installer.iss
; Requires: Inno Setup 6.x from https://jrsoftware.org/isdownload.php

#define MyAppName "QEMU-MCP"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Omarchy VM Control"
#define MyAppURL "https://github.com/omarchy/qemu-mcp"
#define MyAppExeName "QEMU-MCP.exe"
#define MyAppDescription "MCP-powered QEMU Virtual Machine Controller"

[Setup]
; ── Identity & metadata ──────────────────────────────────────────────────
AppId={{6C3A8E8A-9B4F-4D6E-8A2C-1E5F7D9B3A0C}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppVerName={{#MyAppName}} { {#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppPublisherURL={{#MyAppURL}}
AppSupportURL={{#MyAppURL}}/issues
AppUpdatesURL={{#MyAppURL}}/releases

; ── Installation paths ───────────────────────────────────────────────────
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=yes

; ── Compression ──────────────────────────────────────────────────────────
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir=installer-output
OutputBaseFilename=QEMU-MCP-{#MyAppVersion}-setup

; ── UI ───────────────────────────────────────────────────────────────────
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={{#MyAppName}}

; ── Version info embedded in the installer .exe ─────────────────────────
VersionInfoVersion={{#MyAppVersion}}
VersionInfoName={{#MyAppName}}
VersionInfoCompany={{#MyAppPublisher}}
VersionInfoDescription={{#MyAppDescription}}
VersionInfoCopyright=(C) 2025 { {#MyAppPublisher}}
VersionInfoProductName={{#MyAppName}}
VersionInfoProductVersion={{#MyAppVersion}}

; ── Privileges ───────────────────────────────────────────────────────────
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; ── Security: .env is NEVER bundled ──────────────────────────────────────
; .env is created at runtime by the application from user config dir.
; It must not ship inside the installer — secrets, API keys, etc.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; ── Main executable (built by PyInstaller) ──────────────────────────────
; Adjust the Source path if your dist/ lives elsewhere.
Source: "dist\{{#MyAppExeName}}";            DestDir: "{app}"; Flags: ignoreversion

; ── Documentation ────────────────────────────────────────────────────────
Source: "README.md";                         DestDir: "{app}"; Flags: ignoreversion
Source: ".env.example";                      DestDir: "{app}"; Flags: ignoreversion; DestName: "env.example"

; ── QEMU binaries (optional — only if shipping separately) ───────────────
; If PyInstaller already bundled qemu-system-x86_64.exe + qemu-img.exe
; inside the exe, you can skip these two lines.
; Source: "C:\Program Files\qemu\qemu-system-x86_64.exe"; DestDir: "{app}\qemu"; Flags: ignoreversion
; Source: "C:\Program Files\qemu\qemu-img.exe";            DestDir: "{app}\qemu"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";               Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}";    Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
; Optional: record config directory so the app can find user data
Root: HKCU; Subkey: "Software\{{#MyAppName}}"; ValueType: string; ValueName: "ConfigDir"; ValueData: "{userappdata}\{#MyAppName}"

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\{#MyAppName}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    { Preserve .env during uninstall — never delete user secrets. }
    if FileExists(ExpandConstant('{app}\.env')) then
      RenameFile(ExpandConstant('{app}\.env'), ExpandConstant('{app}\.env.uninstall-backup'));
  end;
end;
