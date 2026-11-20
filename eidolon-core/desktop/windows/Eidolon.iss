; ==========================================================
; Projet      : Eidolon Core
; Organisation: Eidolon Core Technologies (ECT)
; Fichier     : Eidolon.iss
; Description : Installation du compagnon par compte Windows
; Standard    : Eidolon Presentation Standard v1
; ==========================================================
#ifndef PayloadDir
  #error PayloadDir is required; use the verified generic Windows build directory.
#endif
#define AppVersion "0.2.0-preview.1"
[Setup]
AppId=ECT.Eidolon.Desktop
AppName=Eidolon
AppVersion={#AppVersion}
AppPublisher=Eidolon Core Technologies (ECT)
AppComments=Local AI • Modular • Reliable • Reproducible
DefaultDirName={localappdata}\Programs\Eidolon
DefaultGroupName=Eidolon
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputBaseFilename=Eidolon-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\Eidolon-compagnon.exe
[Languages]
Name: french; MessagesFile: compiler:Languages\French.isl
[Tasks]
Name: startup; Description: "Démarrer le compagnon à l’ouverture de session (micro inactif)"; Flags: unchecked
Name: desktopicon; Description: "Créer un raccourci sur le bureau"; Flags: unchecked
[Files]
; Explicit public allowlist: never embed connection.json or desktop-identity.
Source: "{#PayloadDir}\Eidolon.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\Eidolon-compagnon.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\eidolon-consultation.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PayloadDir}\Eidolon-camera.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\Eidolon"; Filename: "{app}\Eidolon-compagnon.exe"
Name: "{userdesktop}\Eidolon"; Filename: "{app}\Eidolon-compagnon.exe"; Tasks: desktopicon
Name: "{userstartup}\Eidolon"; Filename: "{app}\Eidolon-compagnon.exe"; Parameters: "--background"; Tasks: startup
[Run]
Filename: "{app}\Eidolon-compagnon.exe"; Parameters: "--background"; Description: "Ouvrir le compagnon Eidolon"; Flags: postinstall nowait skipifsilent
