; Katib installer (Inno Setup 6 or 7). build.bat compiles it from dist\Katib.
;
; Two folders that must never be the same one (ADR-0014):
;   program  {autopf}\Katib        = %LOCALAPPDATA%\Programs\Katib for this per-user install
;   data     {localappdata}\Katib  = settings.json, Models\, Logs\ (ADR-0009)
; Version 1.0.0 installed the program into the data folder and its uninstaller deleted
; that whole folder. The program now has its own folder, and the uninstaller removes only
; the files Setup installed.

#define AppName      "Katib"
#define AppVersion   "1.1.0"
#define AppPublisher "zntkr"
#define AppExeName   "Katib.exe"
#define BuildDir     "dist\Katib"
; The folder core/settings.py::get_app_data_dir() returns (tests/test_installer.py). Setup
; never writes to it or deletes from it; the uninstaller only tells the user where it is.
#define DataDir      "{localappdata}\Katib"

[Setup]
AppId={{A3F2C1D4-7E8B-4F9A-B2C3-D4E5F6A7B8C9}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/zntkr/katib
DefaultDirName={autopf}\{#AppName}
; The program always goes to this one folder: Setup neither asks for a folder nor reuses
; the folder of an older install (1.0.0 lived in the data folder).
UsePreviousAppDir=no
DisableDirPage=yes
DefaultGroupName={#AppName}
AllowNoIcons=yes
; Installer output
OutputDir=installer
OutputBaseFilename=Katib_Setup_{#AppVersion}
SetupIconFile=katib.ico
; Compression
Compression=lzma2/max
SolidCompression=yes
; Windows 10+ required (Direct3D 11 dependency)
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
; UI
WizardStyle=modern
WizardResizable=no
; Uninstall
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; There is no [UninstallDelete] section on purpose. The uninstaller removes what Setup
; installed and nothing else; the user's settings and models stay where they are.

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  // Say where the data is: several GB of models would otherwise stay behind unnoticed.
  DataDir := ExpandConstant('{#DataDir}');
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) and DirExists(DataDir) then
    SuppressibleMsgBox(
      'Your settings and downloaded models were kept in:' + #13#10 + DataDir + #13#10#13#10 +
      'Delete that folder yourself if you no longer need them.',
      mbInformation, MB_OK, IDOK);
end;
