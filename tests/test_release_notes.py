import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packaging"))

from extract_release_notes import FALLBACK, extract_notes  # noqa: E402


def test_extract_existing_version(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## v1.1.0 – 2026-11-15\n\n### Neu\n- OCR für Scans\n\n## v1.0.0\n\n- erste Version\n",
        encoding="utf-8",
    )
    notes = extract_notes("v1.1.0", changelog)
    assert "OCR für Scans" in notes
    assert "erste Version" not in notes  # nächster Abschnitt endet die Sektion
    notes_v1 = extract_notes("v1.0.0", changelog)
    assert "erste Version" in notes_v1


def test_extract_unknown_version_falls_back(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n## v1.0.0\n\n- x\n", encoding="utf-8")
    assert extract_notes("v9.9.9", changelog) == FALLBACK


def test_repo_changelog_has_sections_for_released_tags():
    changelog = Path(__file__).resolve().parent.parent / "CHANGELOG.md"
    assert "## v1.0.0" in changelog.read_text(encoding="utf-8")
    assert "## v1.1.0" in changelog.read_text(encoding="utf-8")
