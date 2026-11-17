"""Prueft das PyInstaller-Bundle der gebauten EXE (CI und lokaler Windows-Build).

Aufruf: python packaging/check_bundle.py packaging/dist/Gideons-Uebersetzer.exe

Prueft:
- llama.dll und ggml-*.dll liegen im Bundle (sonst laedt das lokale Modell nicht)
- python312.dll und das VC++-Runtime (vcruntime140.dll) liegen im Bundle; ohne
  installiertes VC-Redist auf dem Zielrechner startet die EXE sonst nicht mit
  "Failed to load Python DLL ... LoadLibrary: Das angegebene Modul wurde nicht gefunden"
- jede DLL, die die gebündelte python312.dll importiert, ist entweder im Bundle
  selbst oder eine System-DLL, die Windows 10/11 von Haus aus liefert
  (api-ms-win-*, ext-ms-win-*, ucrtbase.dll, kernel32.dll, ...)

Exitcode 0 = alles ok, 1 = Problem (CI schlaegt dann fehl).
"""

from __future__ import annotations

import sys

from PyInstaller.archive.readers import CArchiveReader

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


def python_dll_imports(reader: CArchiveReader, dll_name: str = "python312.dll") -> list[str]:
    """Liest die Import-Tabelle der gebündelten Python-DLL direkt aus dem EXE-Archiv."""
    import pefile

    key = next((n for n in reader.toc if n.replace(BS, "/").lower() == dll_name), None)
    if key is None:
        return []
    pe = pefile.PE(data=reader.extract(key))
    imports = []
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        dll = entry.dll.decode("ascii", "replace") if isinstance(entry.dll, bytes) else str(entry.dll)
        imports.append(dll)
    pe.close()
    return imports


def main(exe_path: str) -> int:
    reader = CArchiveReader(exe_path)
    names = [n.replace(BS, "/") for n in reader.toc]
    dlls = [n for n in names if n.lower().endswith(".dll")]
    print(f"{len(names)} Eintraege, {len(dlls)} DLLs im Bundle")

    problems: list[str] = []
    if not any(n.endswith("llama.dll") for n in dlls):
        problems.append("llama.dll fehlt im Bundle")
    if not any("ggml" in n.lower() for n in dlls):
        problems.append("ggml-DLLs fehlen im Bundle")
    lower_dlls = {n.lower() for n in dlls}
    for required in ("python312.dll", "vcruntime140.dll"):
        if required not in lower_dlls:
            problems.append(f"{required} fehlt im Bundle (EXE startet ohne VC-Redist auf dem Zielrechner nicht)")

    if "python312.dll" in lower_dlls:
        imports = python_dll_imports(reader)
        print("python312.dll importiert:", ", ".join(sorted(set(imports))))
        missing = unsatisfied_imports(imports, dlls)
        if missing:
            problems.append(f"python312.dll importiert DLLs, die weder im Bundle noch System-DLLs sind: {missing}")
        else:
            print("Alle Importe von python312.dll sind im Bundle oder Windows-System-DLLs.")

    interesting = [n for n in dlls if any(k in n.lower() for k in ("python", "vcruntime", "msvcp", "vcomp", "llama", "ggml", "api-ms"))]
    print("Relevante gebündelte DLLs:", ", ".join(sorted(interesting)))

    if problems:
        for p in problems:
            print("FEHLER:", p)
        return 1
    print("Bundle ok")
    return 0


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "packaging/dist/Gideons-Uebersetzer.exe"
    sys.exit(main(path))
