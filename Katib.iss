#define AppName      "Katib"
#define AppVersion   "1.0.0"
#define AppPublisher "zntkr"
#define AppExeName   "Katib.exe"
#define BuildDir     "dist\Katib"

[Setup]
AppId={{A3F2C1D4-7E8B-4F9A-B2C3-D4E5F6A7B8C9}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/zntkr/katib
DefaultDirName={localappdata}\{#AppName}
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
; Tüm build çıktısını kopyala
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#AppName}";          Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; Desktop (opsiyonel)
Name: "{autodesktop}\{#AppName}";    Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Kurulum bittikten sonra çalıştırma seçeneği
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Uygulama ayarlarını silme — kullanıcı verisi korunur (%USERPROFILE%\.katib_app)
Type: filesandordirs; Name: "{app}"
