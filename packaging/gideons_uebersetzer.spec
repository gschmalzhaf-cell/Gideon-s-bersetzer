# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für Gideon's Übersetzer (Windows, eine einzelne .exe).

Aufruf auf dem Windows-Build-Rechner (aus dem Ordner packaging/):
    pyinstaller gideons_uebersetzer.spec --clean --noconfirm

Ergebnis: dist/Gideons-Uebersetzer.exe

Wichtig: Für CUDA-Beschleunigung muss vorher das CUDA-Build von
llama-cpp-python installiert sein (siehe requirements.txt). collect_all
liefert dann die CUDA-DLLs und die gguf-Bibliothek automatisch mit.
Ohne CUDA-Build bündelt PyInstaller die CPU-Variante – die App läuft dann
mit entsprechender Warnung auf der CPU.
"""

from PyInstaller.utils.hooks import collect_all

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
    "huggingface_hub",
    "requests",
    "pymupdf",
    "ebooklib",
    "llama_cpp",
]

# Native Bibliotheken und Datendateien einsammeln (gguf-Bibliothek, CUDA-DLLs,
# pymupdf-DLLs, OCR: ONNX-Runtime + OpenCV + RapidOCR-Modelle)
for pkg in ("llama_cpp", "pymupdf", "ebooklib", "huggingface_hub", "rapidocr_onnxruntime", "onnxruntime", "cv2"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ["../src/gideons_uebersetzer/app.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
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
