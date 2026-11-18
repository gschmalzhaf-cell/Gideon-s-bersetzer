"""Kuscheliges saisonales Design (Qt-Stylesheet).

Modus "seasonal" (Standard): die Palette wechselt mit der Jahreszeit –
  Herbst  (Sep–Nov): warmes Creme/Amber, Akzent Kastanie      🍂
  Winter  (Dez–Feb): eisiges Blau, Akzent warmes Kerzenrot     ❄️
  Frühling (Mär–Mai): frisches Grün, Akzent Blattgrün           🌸
  Sommer  (Jun–Aug): warmes Sand, Akzent Gold/Teal             ☀️
Daneben fest wählbar: "light" (hell) und "dark" (kuschelig-warmes Dunkel).

Einstellung: Feld "theme" in settings.json, wählbar in den Einstellungen.
"""

from __future__ import annotations

from datetime import date

APP_TITLE = "Gideon's Übersetzer"

# wählbare Modi: (id, Label für die Combo in den Einstellungen)
THEME_CHOICES = [
    ("seasonal", "Automatisch – kuschelig-saisonal"),
    ("light", "Hell"),
    ("dark", "Dunkel (kuschelig)"),
]
THEME_IDS = {tid for tid, _label in THEME_CHOICES}

SEASON_EMOJI = {"autumn": "\U0001F342", "winter": "\u2744\uFE0F", "spring": "\U0001F338", "summer": "\u2600\uFE0F"}
SEASON_NAME_DE = {"autumn": "Herbst", "winter": "Winter", "spring": "Frühling", "summer": "Sommer"}

# Paletten: warme, dezente Töne; Akzentfarbe für Buttons/Auswahl/Fortschritt.
PALETTES = {
    "autumn": {
        "bg_top": "#f7ead6", "bg_bottom": "#eed3b0", "window": "#f9f0e2", "text": "#4a3423",
        "accent": "#b5651d", "accent_hover": "#d07a2e", "accent_pressed": "#8f4f16",
        "field": "#fffaf1", "border": "#d9c0a0", "disabled": "#c9b394", "group": "#f3e5cf",
    },
    "winter": {
        "bg_top": "#e9eff6", "bg_bottom": "#cfdde9", "window": "#eff4f9", "text": "#2c3a4a",
        "accent": "#b04a3a", "accent_hover": "#c75f4e", "accent_pressed": "#8f3a2d",
        "field": "#fbfdff", "border": "#b9c9d8", "disabled": "#a9b8c6", "group": "#e2ebf2",
    },
    "spring": {
        "bg_top": "#eef6e9", "bg_bottom": "#d9ebcf", "window": "#f3f9ee", "text": "#33422c",
        "accent": "#7fa653", "accent_hover": "#93bb66", "accent_pressed": "#678a42",
        "field": "#fcfff8", "border": "#c2d8b0", "disabled": "#b0c4a0", "group": "#e6f1dd",
    },
    "summer": {
        "bg_top": "#fdf3dc", "bg_bottom": "#f6e0b4", "window": "#fdf8ec", "text": "#4d3d20",
        "accent": "#c98a2d", "accent_hover": "#dda244", "accent_pressed": "#a66f22",
        "field": "#fffdf6", "border": "#e3cd9f", "disabled": "#d3bd8e", "group": "#f9eed6",
    },
    "light": {
        "bg_top": "#fbf7f0", "bg_bottom": "#f0e9df", "window": "#fdfaf5", "text": "#3d3630",
        "accent": "#4a7fb5", "accent_hover": "#5f94cc", "accent_pressed": "#3a689a",
        "field": "#ffffff", "border": "#d8cfc4", "disabled": "#c5bcb0", "group": "#f4eee6",
    },
    "dark": {
        "bg_top": "#3a332b", "bg_bottom": "#2a251f", "window": "#332e27", "text": "#f0e6d8",
        "accent": "#e0995a", "accent_hover": "#efae72", "accent_pressed": "#c67f45",
        "field": "#403a31", "border": "#5c5347", "disabled": "#6b6255", "group": "#3a342c",
    },
}

_QSS_TEMPLATE = """
QMainWindow, QDialog {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 __BG_TOP__, stop:1 __BG_BOTTOM__);
}
#central { background: transparent; }
QWidget {
    color: __TEXT__;
    background: transparent;
    font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif;
}
QLabel, QCheckBox, QRadioButton { background: transparent; color: __TEXT__; }
QPushButton {
    background-color: __ACCENT__;
    color: #ffffff;
    border: none;
    border-radius: 9px;
    padding: 7px 16px;
    font-weight: 600;
}
QPushButton:hover { background-color: __ACCENT_HOVER__; }
QPushButton:pressed { background-color: __ACCENT_PRESSED__; }
QPushButton:disabled { background-color: __DISABLED__; color: #f5f0e8; }
QLineEdit, QPlainTextEdit, QListWidget, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: __FIELD__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    border-radius: 7px;
    padding: 5px 8px;
}
QLineEdit:focus, QPlainTextEdit:focus, QListWidget:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid __ACCENT__;
}
QComboBox QAbstractItemView {
    background-color: __FIELD__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    selection-background-color: __ACCENT__;
    selection-color: #ffffff;
}
QListWidget::item { padding: 4px; border-radius: 5px; }
QListWidget::item:selected { background-color: __ACCENT__; color: #ffffff; }
QProgressBar {
    background-color: __FIELD__;
    border: 1px solid __BORDER__;
    border-radius: 8px;
    text-align: center;
    color: __TEXT__;
    min-height: 16px;
}
QProgressBar::chunk { background-color: __ACCENT__; border-radius: 7px; }
QGroupBox {
    background-color: __GROUP__;
    border: 1px solid __BORDER__;
    border-radius: 10px;
    margin-top: 12px;
    padding: 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 5px;
    color: __ACCENT__;
}
QToolTip {
    background-color: __FIELD__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    border-radius: 6px;
    padding: 6px;
}
QDialogButtonBox QPushButton { min-width: 90px; }
QMenu { background-color: __FIELD__; color: __TEXT__; border: 1px solid __BORDER__; }
QMenu::item:selected { background-color: __ACCENT__; color: #ffffff; }
"""


def season_for_date(d: date) -> str:
    """Jahreszeit zu einem Datum: winter (Dez–Feb), spring (Mär–Mai), summer (Jun–Aug), autumn (Sep–Nov)."""
    m = d.month
    if m in (12, 1, 2):
        return "winter"
    if m in (3, 4, 5):
        return "spring"
    if m in (6, 7, 8):
        return "summer"
    return "autumn"


def palette_for(mode: str = "seasonal", today: date | None = None) -> dict:
    """Palette zum Modus; 'seasonal' loest sich ueber das Datum auf; Unbekanntes faellt auf 'seasonal' zurueck."""
    if mode not in PALETTES:
        mode = "seasonal"
    if mode == "seasonal":
        mode = season_for_date(today or date.today())
    return PALETTES[mode]


def season_label(mode: str = "seasonal", today: date | None = None) -> str:
    """z. B. '🍂 Herbst' im saisonalen Modus, sonst leer."""
    if mode != "seasonal":
        return ""
    season = season_for_date(today or date.today())
    return f"{SEASON_EMOJI[season]} {SEASON_NAME_DE[season]}"


def stylesheet_for(mode: str = "seasonal", today: date | None = None) -> str:
    """Qt-Stylesheet (QSS) zur Palette."""
    p = palette_for(mode, today)
    css = _QSS_TEMPLATE
    for key, value in p.items():
        css = css.replace(f"__{key.upper()}__", value)
    return css


def window_title(mode: str = "seasonal", today: date | None = None) -> str:
    """Fenstertitel; im saisonalen Modus mit Jahreszeiten-Emoji."""
    if mode == "seasonal":
        season = season_for_date(today or date.today())
        return f"{SEASON_EMOJI[season]} {APP_TITLE}"
    return APP_TITLE


def apply_theme(qapp, mode: str = "seasonal", today: date | None = None) -> None:
    """Wendet das Stylesheet auf die gesamte QApplication an (alle Fenster + Dialoge)."""
    qapp.setStyleSheet(stylesheet_for(mode, today))
