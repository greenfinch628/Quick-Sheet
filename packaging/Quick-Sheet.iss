[Setup]
AppId=com.greenfinch628.QuickSheet
AppName=Quick-Sheet
AppVersion={#AppVersion}
AppPublisher=Quick-Sheet
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Quick-Sheet
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0.22000
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\Quick-Sheet.exe
SetupIconFile=..\assets\Quick-Sheet.ico
OutputDir=..\windows-build\release
OutputBaseFilename=Quick-Sheet-Setup-{#AppVersion}
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\windows-build\dist\Quick-Sheet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Quick-Sheet"; Filename: "{app}\Quick-Sheet.exe"; WorkingDir: "{app}"
Name: "{userdesktop}\Quick-Sheet"; Filename: "{app}\Quick-Sheet.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Quick-Sheet.exe"; Description: "Launch Quick-Sheet"; Flags: nowait postinstall skipifsilent

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Shell, Link: Variant;
  Shortcut, Launcher, Folder, Source, Destination: String;
begin
  Result := '';
  Destination := ExpandConstant('{userappdata}\Quick-Sheet\session.json');
  Shortcut := ExpandConstant('{userprograms}\Quick-Sheet.lnk');
  if FileExists(Destination) or not FileExists(Shortcut) then
    Exit;
  try
    Shell := CreateOleObject('WScript.Shell');
    Link := Shell.CreateShortcut(Shortcut);
    if CompareText(ExtractFileName(Link.TargetPath), 'wscript.exe') <> 0 then
      Exit;
    Launcher := RemoveQuotes(Link.Arguments);
    if CompareText(ExtractFileName(Launcher), 'Launch.vbs') <> 0 then
      Exit;
    Folder := ExtractFileDir(Launcher);
    Source := AddBackslash(Folder) + '.mini-session.json';
    if FileExists(Launcher) and FileExists(AddBackslash(Folder) + 'app_info.py') and
      FileExists(Source) then
    begin
      if not ForceDirectories(ExtractFileDir(Destination)) then
        RaiseException('Could not create the Quick-Sheet user data directory.');
      if not CopyFile(Source, Destination, True) and not FileExists(Destination) then
        RaiseException('Could not copy the existing Quick-Sheet session.');
    end;
  except
    Result := GetExceptionMessage;
  end;
end;
