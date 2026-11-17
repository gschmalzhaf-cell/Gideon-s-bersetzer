@echo off
REM Build-Skript für Windows: erzeugt dist\Tolino-Uebersetzer-Setup-<Version>.exe
REM (Version = oberster CHANGELOG-Abschnitt "## vX.Y.Z"; wird per /DMyAppVersion=...
REM an Inno Setup übergeben, damit der Installer-Dateiname die Version trägt.)
REM Voraussetzung: Python 3.12 installiert, Inno Setup 6 installiert,
REM CUDA-Build von llama-cpp-python (optional, siehe requirements.txt).
setlocal
cd /d %~dp0\..

python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

REM Version aus dem obersten CHANGELOG-Abschnitt lesen (erste Zeile "## vX.Y.Z")
for /f "delims=" %%i in ('findstr /r "^## v[0-9]" CHANGELOG.md') do if not defined VERSION set "VERSION=%%i"
for /f "tokens=2 delims= " %%j in ("%VERSION%") do set "VERSION=%%j"
set VERSION=%VERSION:v=%
if not defined VERSION (
  echo Keine Version in CHANGELOG.md gefunden. 1>&2
  exit /b 1
)
echo Version: %VERSION%

REM distpath muss packaging\dist sein, damit installer.iss die EXE findet
pyinstaller packaging\gideons_uebersetzer.spec --clean --noconfirm --distpath packaging\dist --workpath build\pyinstaller
if errorlevel 1 goto :error

REM Bundle pruefen (llama.dll, python312.dll, VC-Runtime, Importe)
python packaging\check_bundle.py packaging\dist\Gideons-Uebersetzer.exe
if errorlevel 1 goto :error

REM Inno Setup: ISCC.exe liegt normalerweise unter "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "/DMyAppVersion=\"%VERSION%\"" packaging\installer.iss
if errorlevel 1 goto :error
ren "packaging\dist\Tolino-Uebersetzer-Setup.exe" "Tolino-Uebersetzer-Setup-%VERSION%.exe"
if errorlevel 1 goto :error

echo.
echo Fertig: packaging\dist\Tolino-Uebersetzer-Setup-%VERSION%.exe
goto :eof

:error
echo BUILD FEHLGESCHLAGEN 1>&2
exit /b 1
