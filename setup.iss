[Setup]
AppName=OmniGrab
AppVersion=1.0.0
DefaultDirName={autopf}\OmniGrab
DefaultGroupName=OmniGrab
OutputDir=.
OutputBaseFilename=OmniGrab.Setup.1.0.0
Compression=lzma
SolidCompression=yes
SetupIconFile=assets\icon.ico

[Files]
Source: "dist\OmniGrab\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\OmniGrab"; Filename: "{app}\OmniGrab.exe"; IconFilename: "{app}\icon.ico"
Name: "{commondesktop}\OmniGrab"; Filename: "{app}\OmniGrab.exe"; IconFilename: "{app}\icon.ico"
