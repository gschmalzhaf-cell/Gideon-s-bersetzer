import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_installer_iss_mit_version_define():
    iss = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    assert "#ifndef MyAppVersion" in iss
    assert "AppVersion={#MyAppVersion}" in iss
    assert "OutputBaseFilename=Tolino-Uebersetzer-Setup" in iss


def test_ci_uebergibt_version_an_iscc_und_benennt_installer_um():
    wf = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")
    assert "/DMyAppVersion=" in wf
    assert "${{ steps.version.outputs.version }}" in wf
    assert "SETUP_FILE=Tolino-Uebersetzer-Setup-$v.exe" in wf
    assert "Rename-Item" in wf and "$env:SETUP_FILE" in wf
    assert "path: packaging/dist/${{ env.SETUP_FILE }}" in wf
    assert 'find artifact -name "Tolino-Uebersetzer-Setup-*.exe"' in wf


def test_bat_uebergibt_version_an_iscc_und_benennt_um():
    bat = (ROOT / "packaging" / "build-windows.bat").read_text(encoding="utf-8")
    assert "/DMyAppVersion=" in bat
    assert "Tolino-Uebersetzer-Setup-%VERSION%.exe" in bat


def test_spec_sammelt_native_dlls_einzeln_pro_collector():
    spec = (ROOT / "packaging" / "gideons_uebersetzer.spec").read_text(encoding="utf-8")
    assert "collect_dynamic_libs" in spec
    assert "collect_data_files" in spec
    assert "collect_submodules" in spec


def test_ci_kein_cuda_wheel_im_release_build_und_bundle_check():
    wf = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")
    assert "abetlen.github.io" not in wf
    assert "llama_supports_gpu_offload" in wf
    assert "check_bundle.py packaging/dist/Gideons-Uebersetzer" in wf
    check = (ROOT / "packaging" / "check_bundle.py").read_text(encoding="utf-8")
    assert "CArchiveReader" in check
    assert "llama.dll" in check and "ggml" in check
    assert "python312.dll" in check and "vcruntime140.dll" in check


def test_spec_buendelt_vc_runtime_dlls_explizit():
    spec = (ROOT / "packaging" / "gideons_uebersetzer.spec").read_text(encoding="utf-8")
    assert "vcruntime140" in spec and "msvcp140" in spec
    assert "sys.base_prefix" in spec


def test_check_bundle_import_pruefung():
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_bundle", ROOT / "packaging" / "check_bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.is_os_provided("api-ms-win-crt-runtime-l1-1-0.dll")
    assert mod.is_os_provided("ext-ms-win-rtcore-ntuser-window-ext-l1-1-0.dll")
    assert mod.is_os_provided("ucrtbase.dll")
    assert not mod.is_os_provided("vcruntime140.dll")
    assert mod.unsatisfied_imports(["VCRUNTIME140.dll", "KERNEL32.dll", "api-ms-win-core-x.dll"],
                                   ["python312.dll", "vcruntime140.dll"]) == []
    assert mod.unsatisfied_imports(["SOMETHING.dll"], ["python312.dll"]) == ["SOMETHING.dll"]


def test_changelog_oberster_abschnitt_ist_semver():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    top = re.findall(r"^## (v\d+\.\d+\.\d+)", changelog, flags=re.M)[0]
    assert re.fullmatch(r"v\d+\.\d+\.\d+", top)


def test_app_version_matches_changelog_top():
    import re

    import gideons_uebersetzer

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    top = re.findall(r"^## (v\d+\.\d+\.\d+)", changelog, flags=re.M)[0]
    assert gideons_uebersetzer.__version__ == top[1:]
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{top[1:]}"' in pyproject


def test_spec_onedir_collect():
    spec = (ROOT / "packaging" / "gideons_uebersetzer.spec").read_text(encoding="utf-8")
    assert "COLLECT(" in spec
    assert "exclude_binaries=True" in spec
    assert "gideons_uebersetzer.theme" in spec  # Theme-Modul im Bundle


def test_installer_iss_installiert_ganzen_app_ordner():
    iss = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    assert "dist" + chr(92) + "Gideons-Uebersetzer" + chr(92) + "*" in iss
    assert "recursesubdirs" in iss


def test_check_bundle_onedir_hilfsfunktionen(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_bundle_dir", ROOT / "packaging" / "check_bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    internal = tmp_path / "_internal"
    (internal / "llama_cpp" / "lib").mkdir(parents=True)
    (internal / "llama_cpp" / "lib" / "llama.dll").write_bytes(b"x")
    (internal / "llama_cpp" / "lib" / "ggml-cpu.dll").write_bytes(b"x")
    (internal / "python312.dll").write_bytes(b"x")
    (internal / "vcruntime140.dll").write_bytes(b"x")
    dlls = mod.dll_names_from_dir(str(tmp_path))
    assert "_internal/python312.dll" in dlls
    assert "_internal/llama_cpp/lib/llama.dll" in dlls
    assert mod.find_file(str(tmp_path), "vcruntime140.dll").endswith("vcruntime140.dll")
    assert mod.find_file(str(tmp_path), "fehlt.dll") is None
