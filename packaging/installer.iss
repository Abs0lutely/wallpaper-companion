#ifndef AppVersion
  #error AppVersion must be supplied by the build script
#endif
#ifndef BundleDir
  #error BundleDir must be supplied by the build script
#endif
#ifndef ReleaseDir
  #error ReleaseDir must be supplied by the build script
#endif

[Setup]
AppId={{7D64A36F-58DA-47D5-9BC7-3F10CD22D328}
AppName=Wallpaper Companion
AppVersion={#AppVersion}
AppPublisher=Wallpaper Companion contributors
AppPublisherURL=https://github.com/Abs0lutely/wallpaper-companion
AppSupportURL=https://github.com/Abs0lutely/wallpaper-companion/issues
DefaultDirName={localappdata}\Programs\WallpaperCompanion
DefaultGroupName=Wallpaper Companion
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ReleaseDir}
OutputBaseFilename=WallpaperCompanion-{#AppVersion}-windows-x64-setup
SetupIconFile=..\build\app.ico
UninstallDisplayIcon={app}\WallpaperCompanion.exe
LicenseFile=..\LICENSE
WizardStyle=modern
Compression=lzma2/normal
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "\portable.flag,\data\*,\shared\*,\plugins\*.py"

[Dirs]
Name: "{app}\shared"; Flags: uninsneveruninstall

[Icons]
Name: "{group}\Wallpaper Companion"; Filename: "{app}\WallpaperCompanion.exe"; WorkingDir: "{app}"
Name: "{group}\User guide"; Filename: "{app}\USER_GUIDE.md"
Name: "{autodesktop}\Wallpaper Companion"; Filename: "{app}\WallpaperCompanion.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WallpaperCompanion.exe"; Description: "Launch Wallpaper Companion"; Flags: nowait postinstall skipifsilent

; User data and external resources are intentionally never removed.
; Only remove our optional startup value if it points to this installation.
[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Value: String;
begin
  if CurUninstallStep = usUninstall then
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'WallpaperVoiceCompanion', Value) then
      if (CompareText(Value, '"' + ExpandConstant('{app}\WallpaperCompanion.exe') + '" --tray') = 0) or
         (CompareText(Value, ExpandConstant('{app}\WallpaperCompanion.exe') + ' --tray') = 0) then
        RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'WallpaperVoiceCompanion');
end;
