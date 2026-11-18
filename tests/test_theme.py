"""Tests für das kuschelige saisonale Design (theme.py) und das Settings-Feld 'theme'."""

import json
from datetime import date

from gideons_uebersetzer import theme
from gideons_uebersetzer.settings import Settings, load_settings


def test_season_boundaries():
    assert theme.season_for_date(date(2026, 11, 18)) == "autumn"  # aktuell: November
    assert theme.season_for_date(date(2026, 9, 1)) == "autumn"
    assert theme.season_for_date(date(2026, 12, 1)) == "winter"
    assert theme.season_for_date(date(2027, 1, 15)) == "winter"
    assert theme.season_for_date(date(2027, 2, 28)) == "winter"
    assert theme.season_for_date(date(2027, 3, 1)) == "spring"
    assert theme.season_for_date(date(2027, 5, 31)) == "spring"
    assert theme.season_for_date(date(2027, 6, 21)) == "summer"
    assert theme.season_for_date(date(2027, 8, 31)) == "summer"


def test_stylesheet_uses_season_palette_and_cozy_bits():
    css = theme.stylesheet_for("seasonal", today=date(2026, 11, 18))
    p = theme.PALETTES["autumn"]
    assert p["accent"] in css
    assert p["bg_top"] in css and p["bg_bottom"] in css
    assert "QPushButton" in css and "border-radius" in css and "qlineargradient" in css
    # Winter-Palette ist eine andere als Herbst
    assert theme.PALETTES["winter"]["accent"] in theme.stylesheet_for("seasonal", today=date(2026, 12, 24))


def test_stylesheet_modes_and_fallback():
    assert theme.stylesheet_for("light") != theme.stylesheet_for("dark")
    # unbekannter Modus fällt auf "seasonal" zurück
    assert theme.stylesheet_for("kaputt", today=date(2026, 11, 18)) == theme.stylesheet_for("seasonal", today=date(2026, 11, 18))
    # gleiches Datum -> gleiches Stylesheet (deterministisch testbar)
    assert theme.stylesheet_for("seasonal", today=date(2026, 11, 18)) == theme.stylesheet_for("seasonal", today=date(2026, 11, 30))
    # alle Paletten-Platzhalter sind ersetzt
    css = theme.stylesheet_for("dark")
    assert "__" not in css


def test_season_label_and_window_title():
    label = theme.season_label("seasonal", today=date(2026, 11, 18))
    assert "Herbst" in label and theme.SEASON_EMOJI["autumn"] in label
    assert theme.season_label("dark", today=date(2026, 11, 18)) == ""
    assert theme.window_title("light") == "Gideon's Übersetzer"
    assert "Gideon's Übersetzer" in theme.window_title("seasonal", today=date(2026, 11, 18))
    assert theme.SEASON_EMOJI["autumn"] in theme.window_title("seasonal", today=date(2026, 11, 18))


def test_settings_theme_default_and_normalization(tmp_path):
    assert Settings().theme == "seasonal"
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"theme": "kaputt"}), encoding="utf-8")
    assert load_settings(p).theme == "seasonal"
    p.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    assert load_settings(p).theme == "dark"
    p.write_text(json.dumps({}), encoding="utf-8")
    assert load_settings(p).theme == "seasonal"
