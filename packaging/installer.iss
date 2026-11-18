; Inno-Setup-Skript für Gideon's Übersetzer (Windows 10/11, 64 Bit).
;
; Build auf dem Windows-Rechner:
;   1. PyInstaller:  pyinstaller packaging\gideons_uebersetzer.spec --clean --noconfirm
;   2. Inno Setup 6: kompiliert packaging\installer.iss
;      -> dist\Tolino-Uebersetzer-Setup.exe; CI/build-windows.bat benennen die fertige
;        Datei danach um in Tolino-Uebersetzer-Setup-<Version>.exe (Version per ISCC
;        /DMyAppVersion="<Version>"; ohne Angabe Fallback unten)
;
; Der Installer enthält NICHT das Übersetzungsmodell (ca. 4,4 GB): Die Anwendung
; lädt es beim ersten Start selbst herunter (Assistent, Offline-Weg an erster Stelle).

#define MyAppName "Gideon's Übersetzer"
#ifndef MyAppVersion
#define MyAppVersion "1.2.5"
#endif
#define MyAppPublisher "Gideon's Übersetzer"
#define MyAppExeName "Gideons-Uebersetzer.exe"
#define MyAppURL "https://github.com/gschmalzhaf-cell/Gideon-s-bersetzer"

[Setup]
AppId={{7F3A9C21-5E4B-4D8A-9C6E-2B1F0A8D3E57}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Gideons-Uebersetzer
DefaultGroupName={#MyAppName}
OutputDir=dist
OutputBaseFilename=Tolino-Uebersetzer-Setup
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardImageFile=wizard_banner.bmp
WizardSmallImageFile=wizard_small.bmp
WizardSizePercent=115
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes
LicenseFile=
InfoBeforeFile=README-de.txt

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "dist\Gideons-Uebersetzer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README-de.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Gideon's Übersetzer"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{group}\README (deutsch)"; Filename: "{app}\README-de.txt"
Name: "{autodesktop}\Gideon's Übersetzer"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Gideon's Übersetzer jetzt starten (Erststart-Assistent lädt das Modell)"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard();
begin
  { Kuscheliges App-Design im Installer übernehmen: warme Creme-/Kastanien-Palette
    (BGR-Format in Pascal: $00BBGGRR -> Creme #F9F0E2 = $00E2F0F9, Feld #FFFAF1 = $00F1FAFF,
    Dunkelbraun #4A3423 = $0023344A, Akzent Kastanie #B5651D = $001D65B5). }
  WizardForm.Color := $00E2F0F9;
  WizardForm.WelcomePage.Color := $00E2F0F9;
  WizardForm.InnerPage.Color := $00E2F0F9;
  WizardForm.MainPanel.Color := $00D6EAF7;
  WizardForm.FinishedPage.Color := $00E2F0F9;

  WizardForm.Font.Name := 'Segoe UI';
  WizardForm.Font.Color := $0023344A;

  WizardForm.WelcomeLabel1.Font.Color := $001D65B5;
  WizardForm.WelcomeLabel2.Font.Color := $0023344A;
  WizardForm.PageNameLabel.Font.Color := $001D65B5;
  WizardForm.PageDescriptionLabel.Font.Color := $0023344A;
  WizardForm.FinishedHeadingLabel.Font.Color := $001D65B5;
  WizardForm.FinishedLabel.Font.Color := $0023344A;

  WizardForm.InfoBeforeMemo.Color := $00F1FAFF;
  WizardForm.InfoBeforeMemo.Font.Name := 'Consolas';
  WizardForm.InfoBeforeMemo.Font.Color := $0023344A;
end;

