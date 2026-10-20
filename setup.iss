; Script tao bo cai dat Inno Setup cho ung dung OmniGrab
; Ho tro Windows 10/11 x64, tu dong tich hop FFmpeg, FFprobe va tat ca thu vien

#define MyAppName "OmniGrab"
#ifndef MyAppVersion
  #define MyAppVersion "4.0.1"
#endif
#define MyAppPublisher "OmniGrab Team"
#define MyAppURL "https://github.com/phamtuandat2005/OmniGrab"
#define MyAppExeName "OmniGrab.exe"
#define MyAppID "OmniGrab.VideoDownloader.1.0"
#ifndef AppDistDir
  #define AppDistDir "dist"
#endif

[Setup]
AppId={{D37B5C19-9B96-4F2A-85C1-285226E6F90E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
AllowNoIcons=yes
OutputDir=dist_installer
OutputBaseFilename=OmniGrab.Setup.{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/fast
SolidCompression=no
LZMAUseSeparateProcess=yes
WizardStyle=modern
DisableWelcomePage=no
DisableProgramGroupPage=yes
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Dirs]
Name: "{commonappdata}\OmniGrab"; Permissions: users-modify

[InstallDelete]
; Xoa shortcut cu co the bi luu sai IconLocation vao thu muc Temp
Type: files; Name: "{userprograms}\OmniGrab.lnk"

[Files]
; Sao chep toan bo thu muc phan phoi da dong goi gom file .exe, thu vien, ffmpeg, ffprobe, assets
Source: "{#AppDistDir}\OmniGrab\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; AppUserModelID: "{#MyAppID}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; AppUserModelID: "{#MyAppID}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
