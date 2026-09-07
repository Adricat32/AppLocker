#define AppVersion "1.0.0"

[Setup]
AppId={{B0A4C8C5-2A3D-4E42-9C66-APPLOCKER2026}
AppName=App Locker
AppVersion={#AppVersion}
AppPublisher=App Locker
DefaultDirName={autopf}\App Locker
DefaultGroupName=App Locker
OutputDir=installer
OutputBaseFilename=AppLocker-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\AppLocker.exe

[Files]
Source: "AppLocker.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\App Locker"; Filename: "{app}\AppLocker.exe"
Name: "{autodesktop}\App Locker"; Filename: "{app}\AppLocker.exe"

[Run]
Filename: "{app}\AppLocker.exe"; Description: "Abrir App Locker"; Flags: nowait postinstall skipifsilent

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
	ResultCode: Integer;
begin
	Exec(ExpandConstant('{cmd}'), '/C taskkill /F /T /IM AppLocker.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
	Result := '';
end;
