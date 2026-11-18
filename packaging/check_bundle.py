"""Prueft das PyInstaller-Bundle (CI und lokaler Windows-Build) – Onedir-Ordner oder Onefile-EXE.

Aufruf:
    python packaging/check_bundle.py packaging/dist/Gideons-Uebersetzer            # Onedir (App-Ordner)
    python packaging/check_bundle.py .../Gideons-Uebersetzer/Gideons-Uebersetzer.exe  # Onefile-EXE

Prueft:
- llama.dll und ggml-*.dll liegen im Bundle (sonst laedt das lokale Modell nicht)
- python312.dll und vcruntime140.dll liegen im Bundle; ohne installiertes VC-Redist auf
  dem Zielrechner startet die App sonst nicht mit
  "Failed to load Python DLL ... LoadLibrary: Das angegebene Modul wurde nicht gefunden"
- jede DLL, die python312.dll importiert, ist im Bundle oder eine System-DLL, die
  Windows 10/11 von Haus aus liefert (api-ms-win-*, ext-ms-win-*, ucrtbase.dll, ...)

Exitcode 0 = alles ok, 1 = Problem (CI schlaegt dann fehl).
"""

from __future__ import annotations

import os
import sys

BS = chr(92)  # Backslash (im Source vermeiden, damit das Skript ueberall gleich bleibt)

# DLLs, die Windows 10/11 selbst mitliefert und die PyInstaller deshalb nicht bündeln darf.
OS_PROVIDED_PREFIXES = ("api-ms-win-", "ext-ms-win-")
OS_PROVIDED_NAMES = {
    "kernel32.dll", "advapi32.dll", "user32.dll", "gdi32.dll", "shell32.dll",
    "ole32.dll", "oleaut32.dll", "ws2_32.dll", "rpcrt4.dll", "combase.dll",
    "ucrtbase.dll", "ntdll.dll", "msvcrt.dll", "secur32.dll", "crypt32.dll",
    "bcrypt.dll", "wintrust.dll", "version.dll", "shlwapi.dll", "shcore.dll",
    "psapi.dll", "dbghelp.dll", "userenv.dll", "powrprof.dll", "cfgmgr32.dll",
    "devobj.dll", "wtsapi32.dll", "imm32.dll", "usp10.dll", "cryptbase.dll",
    "winmm.dll", "dwmapi.dll", "uxtheme.dll", "opengl32.dll", "glu32.dll",
}


def is_os_provided(dll_name: str) -> bool:
    n = dll_name.lower()
    return n.startswith(OS_PROVIDED_PREFIXES) or n in OS_PROVIDED_NAMES


def unsatisfied_imports(imports, bundle_names) -> list[str]:
    """Importe, die weder im Bundle liegen noch System-DLLs sind."""
    bundle = {n.lower().replace(BS, "/").split("/")[-1] for n in bundle_names}
    missing = []
    for imp in imports:
        base = imp.lower().replace(BS, "/").split("/")[-1]
        if base not in bundle and not is_os_provided(base):
            missing.append(imp)
    return missing


def dll_names_from_dir(root: str) -> list[str]:
    """Alle DLLs unterhalb von root (Onedir: payload liegt in _internal/), als rel. Pfade mit '/'."""
    names = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for f in filenames:
            if f.lower().endswith(".dll"):
                names.append(os.path.relpath(os.path.join(dirpath, f), root).replace(BS, "/"))
    return names


def find_file(root: str, basename_lower: str) -> str | None:
    for dirpath, _dirnames, filenames in os.walk(root):
        for f in filenames:
            if f.lower() == basename_lower:
                return os.path.join(dirpath, f)
    return None


def imports_from_file(path: str) -> list[str]:
    """Import-Tabelle einer PE-Datei (pefile wird erst hier importiert, damit Unit-Tests ohne pefile laufen)."""
    import pefile

    pe = pefile.PE(path)
    imports = []
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        dll = entry.dll.decode("ascii", "replace") if isinstance(entry.dll, bytes) else str(entry.dll)
        imports.append(dll)
    pe.close()
    return imports


def imports_from_archive(exe_path: str) -> list[str]:
    """Import-Tabelle der python312.dll direkt aus einer Onefile-EXE (CArchive) lesen."""
    import tempfile

    from PyInstaller.archive.readers import CArchiveReader

    reader = CArchiveReader(exe_path)
    key = next((n for n in reader.toc if n.replace(BS, "/").lower() == "python312.dll"), None)
    if key is None:
        return []
    data = reader.extract(key)
    with tempfile.NamedTemporaryFile(suffix=".dll", delete=False) as tf:
        tf.write(data)
        tmp = tf.name
    try:
        return imports_from_file(tmp)
    finally:
        os.unlink(tmp)


def main(path: str) -> int:
    if os.path.isdir(path):
        dlls = dll_names_from_dir(path)
        total = sum(len(files) for _r, _d, files in os.walk(path))
        print(f"Onedir-Bundle {path}: {total} Dateien, {len(dlls)} DLLs")
        py_file = find_file(path, "python312.dll")
        imports = imports_from_file(py_file) if py_file else []
    else:
        from PyInstaller.archive.readers import CArchiveReader

        reader = CArchiveReader(path)
        names = [n.replace(BS, "/") for n in reader.toc]
        dlls = [n for n in names if n.lower().endswith(".dll")]
        print(f"{len(names)} Eintraege, {len(dlls)} DLLs im Bundle")
        imports = imports_from_archive(path) if "python312.dll" in {n.lower() for n in dlls} else []

    problems: list[str] = []
    bases = {n.lower().split("/")[-1] for n in dlls}
    if "llama.dll" not in bases:
        problems.append("llama.dll fehlt im Bundle")
    if not any("ggml" in b for b in bases):
        problems.append("ggml-DLLs fehlen im Bundle")
    for required in ("python312.dll", "vcruntime140.dll"):
        if required not in bases:
            problems.append(f"{required} fehlt im Bundle (App startet ohne VC-Redist auf dem Zielrechner nicht)")

    if imports:
        print("python312.dll importiert:", ", ".join(sorted(set(imports))))
        missing = unsatisfied_imports(imports, dlls)
        if missing:
            problems.append(f"python312.dll importiert DLLs, die weder im Bundle noch System-DLLs sind: {missing}")
        else:
            print("Alle Importe von python312.dll sind im Bundle oder Windows-System-DLLs.")

    interesting = [n for n in dlls if any(k in n.lower() for k in ("python", "vcruntime", "msvcp", "vcomp", "llama", "ggml", "api-ms"))]
    print("Relevante gebuendelte DLLs:", ", ".join(sorted(interesting)))

    if problems:
        for p in problems:
            print("FEHLER:", p)
        return 1
    print("Bundle ok")
    return 0


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "packaging/dist/Gideons-Uebersetzer"
    sys.exit(main(path))
