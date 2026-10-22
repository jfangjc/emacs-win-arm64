[Setup]
AppId=Emacs-ARM64-{#Channel}
UsePreviousLanguage=no
AppName=GNU Emacs {#EmacsVersion}
AppVerName=GNU Emacs {#EmacsVersion}
AppVersion={#EmacsVersion}
VersionInfoVersion={#NumericVersion}
#if Channel == "stable"
DefaultDirName={localappdata}\Programs\Emacs
#else
DefaultDirName={localappdata}\Programs\Emacs-{#Channel}
#endif
PrivilegesRequired=lowest
ArchitecturesAllowed=arm64
ArchitecturesInstallIn64BitMode=arm64
MinVersion=10.0.22000
LicenseFile=..\emacs-{#EmacsVersion}\COPYING
OutputDir=..\dist
OutputBaseFilename=emacs-{#EmacsVersion}-{#Channel}-windows-arm64-setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\bin\runemacs.exe

[Files]
Source: "..\bin\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Icons]
Name: "{autoprograms}\GNU Emacs {#EmacsVersion}"; Filename: "{app}\bin\runemacs.exe"; WorkingDir: "{userdocs}"
Name: "{autodesktop}\GNU Emacs {#EmacsVersion}"; Filename: "{app}\bin\runemacs.exe"; WorkingDir: "{userdocs}"; Tasks: desktopicon
