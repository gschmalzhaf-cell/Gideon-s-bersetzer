@echo off
REM Build-Skript für Windows: erzeugt dist\Tolino-Uebersetzer-Setup.exe
REM Voraussetzung: Python 3.12 installiert, Inno Setup 6 installiert,
REM CUDA-Build von llama-cpp-python (optional, siehe requirements.txt).
setlocal
cd /d %~dp0\..

python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

pyinstaller packaging\gideons_uebersetzer.spec --clean --noconfirm
if errorlevel 1 goto :error

REM Inno Setup: ISCC.exe liegt normalerweise unter "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
if errorlevel 1 goto :error

echo.
echo Fertig: dist\Tolino-Uebersetzer-Setup.exe
goto :eof

:error
echo BUILD FEHLGESCHLAGEN 1>&2
exit /b 1
