# -*- mode: python ; coding: utf-8 -*-
r"""PyInstaller-Spec für Gideon's Übersetzer (Windows, Onedir: App-Ordner statt einer einzelnen EXE).

Aufruf auf dem Windows-Build-Rechner (aus dem Ordner packaging/):
    pyinstaller gideons_uebersetzer.spec --clean --noconfirm

Ergebnis: dist/Gideons-Uebersetzer/  mit  Gideons-Uebersetzer.exe + _internal/
Onedir statt Onefile: Beim Onefile-Build entpackt sich die EXE bei jedem Start nach
%TEMP%\_MEI... - manche Antiviren (z. B. Windows Defender) quarantähnen dort frisch
entpackte DLLs; dann startet die App nicht ("Failed to load Python DLL ... python312.dll").
Ohne Temp-Extrakt entfällt diese Fehlerquelle.

Wichtig: Für CUDA-Beschleunigung muss vorher das CUDA-Build von
llama-cpp-python installiert sein (siehe requirements.txt). collect_all
liefert dann die CUDA-DLLs und die gguf-Bibliothek automatisch mit.
Ohne CUDA-Build bündelt PyInstaller die CPU-Variante – die App läuft dann
mit entsprechender Warnung auf der CPU.
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

SPEC_DIR = SPECPATH  # Ordner der .spec-Datei (packaging/)

datas = []
binaries = []
hiddenimports = [
    "gideons_uebersetzer",
    "gideons_uebersetzer.app",
    "gideons_uebersetzer.main_window",
    "gideons_uebersetzer.wizard",
    "gideons_uebersetzer.cli",
    "gideons_uebersetzer.pipeline",
    "gideons_uebersetzer.pdf_reader",
    "gideons_uebersetzer.ocr_reader",
    "gideons_uebersetzer.epub_builder",
    "gideons_uebersetzer.translator_base",
    "gideons_uebersetzer.translator_local",
    "gideons_uebersetzer.translator_api",
    "gideons_uebersetzer.cache",
    "gideons_uebersetzer.model_manager",
    "gideons_uebersetzer.settings",
    "gideons_uebersetzer.document_reader",
    "gideons_uebersetzer.mistral_ocr",
    "gideons_uebersetzer.report",
    "gideons_uebersetzer.updater",
    "gideons_uebersetzer.theme",
    "huggingface_hub",
    "requests",
    "pymupdf",
    "ebooklib",
    "llama_cpp",
]

# Native Bibliotheken und Datendateien einsammeln (gguf-Bibliothek, CUDA-DLLs,
# pymupdf-DLLs, OCR: ONNX-Runtime + OpenCV + RapidOCR-Modelle)
for pkg in ("llama_cpp", "pymupdf", "ebooklib", "docx", "huggingface_hub", "rapidocr_onnxruntime", "onnxruntime", "cv2"):
    # Pro Collector einzeln absichern: collect_submodules importiert das Paket und kann
    # fehlschlagen, wenn dessen native lib auf dem Build-Rechner nicht laedt; die DLLs
    # (collect_dynamic_libs = reiner Dateiscan) duerfen dadurch nicht verloren gehen.
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass
    try:
        hiddenimports += collect_submodules(pkg)
    except Exception:
        pass

# VC++-Runtime explizit bündeln: python312.dll hängt an vcruntime140.dll. Ohne
# installiertes VC-Redist auf dem Zielrechner startet die EXE sonst nicht
# ("Failed to load Python DLL ... LoadLibrary: Das angegebene Modul wurde nicht gefunden").
# Die DLLs liegen beim python.org-Layout im Stammverzeichnis der Python-Installation.
import glob
import sys

for _dir in {sys.base_prefix, os.path.dirname(sys.executable)}:
    for _pat in ("vcruntime140*.dll", "msvcp140*.dll", "vccorlib140*.dll", "vcomp140*.dll", "concrt140.dll"):
        for _p in glob.glob(os.path.join(_dir, _pat)):
            binaries.append((_p, "."))

a = Analysis(
    [os.path.join(SPEC_DIR, "entry.py")],  # dünner Einstiegspunkt mit absolutem Import (siehe entry.py)
    pathex=[os.path.join(SPEC_DIR, "..", "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # numpy NICHT ausschließen: cv2/onnxruntime/rapidocr (OCR) brauchen es zur Laufzeit!
    excludes=["tkinter", "matplotlib", "pandas", "scipy"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,  # Onedir: Binaries/Daten wandern via COLLECT nach _internal/
    name="Gideons-Uebersetzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX kann die großen CUDA-DLLs beschädigen – sicherheitshalber aus
    console=False,  # GUI-Anwendung, kein Konsolenfenster
    disable_windowed_traceback=False,
    target_arch="x64",
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Gideons-Uebersetzer",
)
