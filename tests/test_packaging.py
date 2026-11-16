import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_installer_dateiname_traegt_version():
    iss = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    assert "OutputBaseFilename=Tolino-Uebersetzer-Setup-{#MyAppVersion}" in iss
    assert "#ifndef MyAppVersion" in iss
    assert 'AppVersion="{#MyAppVersion}"' in iss


def test_ci_uebergibt_version_an_iscc_und_verwendet_versionierten_dateinamen():
    wf = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")
    assert '"/DMyAppVersion=$($steps.version.outputs.version)"' in wf
    assert "SETUP_FILE=Tolino-Uebersetzer-Setup-$v.exe" in wf
    assert "path: packaging/dist/${{ env.SETUP_FILE }}" in wf
    assert 'find artifact -name "Tolino-Uebersetzer-Setup-*.exe"' in wf


def test_bat_uebergibt_version_an_iscc():
    bat = (ROOT / "packaging" / "build-windows.bat").read_text(encoding="utf-8")
    assert '"/DMyAppVersion=%VERSION%"' in bat
    assert "Tolino-Uebersetzer-Setup-%VERSION%.exe" in bat


def test_changelog_oberster_abschnitt_ist_semver():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    top = re.findall(r"^## (v\d+\.\d+\.\d+)", changelog, flags=re.M)[0]
    assert re.fullmatch(r"v\d+\.\d+\.\d+", top)
