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
    assert "CArchiveReader" in wf
    assert "llama.dll" in wf


def test_changelog_oberster_abschnitt_ist_semver():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    top = re.findall(r"^## (v\d+\.\d+\.\d+)", changelog, flags=re.M)[0]
    assert re.fullmatch(r"v\d+\.\d+\.\d+", top)
