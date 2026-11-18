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

# Paletten: warme, dezente Töne; Akzentfarbe für primäre Buttons/Auswahl/Fortschritt;
# sekundäre Buttons erhalten eine ruhige Karten-/Rahmenfarbe, damit die Hauptaktion heraussticht.
PALETTES = {
    "autumn": {
        "bg_top": "#f7ead6", "bg_bottom": "#eed3b0", "window": "#f9f0e2", "text": "#4a3423", "muted": "#7c5e44",
        "accent": "#b5651d", "accent_hover": "#d07a2e", "accent_pressed": "#8f4f16",
        "btn_bg": "#fff7ea", "btn_hover": "#f5e3c8", "btn_pressed": "#ebd2ae",
        "field": "#fffaf1", "border": "#d9c0a0", "disabled": "#c9b394", "group": "#f4e6d0",
    },
    "winter": {
        "bg_top": "#e9eff6", "bg_bottom": "#cfdde9", "window": "#eff4f9", "text": "#2c3a4a", "muted": "#5c7085",
        "accent": "#b04a3a", "accent_hover": "#c75f4e", "accent_pressed": "#8f3a2d",
        "btn_bg": "#f7fafd", "btn_hover": "#e4edf5", "btn_pressed": "#d4e1ed",
        "field": "#fbfdff", "border": "#b9c9d8", "disabled": "#a9b8c6", "group": "#e2ebf2",
    },
    "spring": {
        "bg_top": "#eef6e9", "bg_bottom": "#d9ebcf", "window": "#f3f9ee", "text": "#33422c", "muted": "#5d7352",
        "accent": "#7fa653", "accent_hover": "#93bb66", "accent_pressed": "#678a42",
        "btn_bg": "#f8fcf4", "btn_hover": "#e7f2dc", "btn_pressed": "#d7e8c8",
        "field": "#fcfff8", "border": "#c2d8b0", "disabled": "#b0c4a0", "group": "#e6f1dd",
    },
    "summer": {
        "bg_top": "#fdf3dc", "bg_bottom": "#f6e0b4", "window": "#fdf8ec", "text": "#4d3d20", "muted": "#7d663c",
        "accent": "#c98a2d", "accent_hover": "#dda244", "accent_pressed": "#a66f22",
        "btn_bg": "#fffbf0", "btn_hover": "#f7e9c6", "btn_pressed": "#eedaa9",
        "field": "#fffdf6", "border": "#e3cd9f", "disabled": "#d3bd8e", "group": "#f9eed6",
    },
    "light": {
        "bg_top": "#fbf7f0", "bg_bottom": "#f0e9df", "window": "#fdfaf5", "text": "#3d3630", "muted": "#73685d",
        "accent": "#4a7fb5", "accent_hover": "#5f94cc", "accent_pressed": "#3a689a",
        "btn_bg": "#faf6f0", "btn_hover": "#ede5da", "btn_pressed": "#e0d6c8",
        "field": "#ffffff", "border": "#d8cfc4", "disabled": "#c5bcb0", "group": "#f4eee6",
    },
    "dark": {
        "bg_top": "#3a332b", "bg_bottom": "#2a251f", "window": "#332e27", "text": "#f0e6d8", "muted": "#b8ab99",
        "accent": "#e0995a", "accent_hover": "#efae72", "accent_pressed": "#c67f45",
        "btn_bg": "#474036", "btn_hover": "#544c40", "btn_pressed": "#3d372e",
        "field": "#403a31", "border": "#5c5347", "disabled": "#6b6255", "group": "#363028",
    },
}

_QSS_TEMPLATE = """
QMainWindow, QDialog, QWizard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 __BG_TOP__, stop:1 __BG_BOTTOM__);
}
#central { background: transparent; }
QWidget {
    color: __TEXT__;
    background: transparent;
    font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 10pt;
}
QLabel, QCheckBox, QRadioButton { background: transparent; color: __TEXT__; }
QLabel#headerTitle {
    font-size: 15pt;
    font-weight: 700;
    color: __TEXT__;
}
QLabel#headerSubtitle, QLabel#hintLabel {
    color: __MUTED__;
    font-size: 9.5pt;
}
QLabel#seasonBadge {
    background-color: __BTN_BG__;
    color: __ACCENT__;
    border: 1px solid __BORDER__;
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 10.5pt;
    font-weight: 600;
}
QLabel#modeBadge {
    background-color: __BTN_BG__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    border-radius: 9px;
    padding: 6px 12px;
    font-weight: 600;
}
QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border: 1.5px solid __BORDER__;
    border-radius: 4px;
    background-color: __FIELD__;
}
QCheckBox::indicator:hover { border-color: __ACCENT__; }
QCheckBox::indicator:checked {
    background-color: __ACCENT__;
    border-color: __ACCENT_PRESSED__;
}
QRadioButton { spacing: 8px; }
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid __BORDER__;
    border-radius: 8px;
    background-color: __FIELD__;
}
QRadioButton::indicator:hover { border-color: __ACCENT__; }
QRadioButton::indicator:checked {
    background-color: __ACCENT__;
    border-color: __ACCENT_PRESSED__;
}
/* Sekundäre Buttons: dezent, warm gerahmt */
QPushButton {
    background-color: __BTN_BG__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    border-radius: 9px;
    padding: 6px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: __BTN_HOVER__;
    border-color: __ACCENT__;
}
QPushButton:pressed { background-color: __BTN_PRESSED__; }
QPushButton:disabled {
    background-color: __GROUP__;
    color: __DISABLED__;
    border-color: __BORDER__;
}
/* Primäre Hauptaktions-Buttons (z. B. Übersetzen starten, Modell laden) */
QPushButton#primaryButton, QPushButton[primary="true"] {
    background-color: __ACCENT__;
    color: #ffffff;
    border: 1px solid __ACCENT_PRESSED__;
    border-radius: 10px;
    padding: 8px 20px;
    font-size: 10.5pt;
    font-weight: 700;
}
QPushButton#primaryButton:hover, QPushButton[primary="true"]:hover {
    background-color: __ACCENT_HOVER__;
}
QPushButton#primaryButton:pressed, QPushButton[primary="true"]:pressed {
    background-color: __ACCENT_PRESSED__;
}
QPushButton#primaryButton:disabled, QPushButton[primary="true"]:disabled {
    background-color: __DISABLED__;
    color: #f5f0e8;
    border-color: __DISABLED__;
}
QLineEdit, QPlainTextEdit, QListWidget, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: __FIELD__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    border-radius: 7px;
    padding: 5px 8px;
}
QLineEdit:focus, QPlainTextEdit:focus, QListWidget:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid __ACCENT__;
}
QComboBox::drop-down {
    border: none;
    padding-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: __FIELD__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    selection-background-color: __ACCENT__;
    selection-color: #ffffff;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 6px;
    margin: 1px 2px;
}
QListWidget::item:selected { background-color: __ACCENT__; color: #ffffff; }
QListWidget::item:hover:!selected { background-color: __BTN_HOVER__; }
QProgressBar {
    background-color: __FIELD__;
    border: 1px solid __BORDER__;
    border-radius: 8px;
    text-align: center;
    color: __TEXT__;
    font-weight: 600;
    min-height: 18px;
}
QProgressBar::chunk { background-color: __ACCENT__; border-radius: 7px; }
QGroupBox {
    background-color: __GROUP__;
    border: 1px solid __BORDER__;
    border-radius: 11px;
    margin-top: 10px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: __ACCENT__;
    font-weight: 700;
}
QTabWidget::pane {
    background-color: __GROUP__;
    border: 1px solid __BORDER__;
    border-radius: 9px;
    padding: 6px;
    top: -1px;
}
QTabBar::tab {
    background-color: __BTN_BG__;
    color: __MUTED__;
    border: 1px solid __BORDER__;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 6px 14px;
    margin-right: 4px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background-color: __ACCENT__;
    color: #ffffff;
    border-color: __ACCENT__;
}
QTabBar::tab:hover:!selected {
    background-color: __BTN_HOVER__;
    color: __TEXT__;
}
QToolTip {
    background-color: __FIELD__;
    color: __TEXT__;
    border: 1px solid __BORDER__;
    border-radius: 6px;
    padding: 6px;
}
QDialogButtonBox QPushButton { min-width: 96px; }
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


def create_app_icon(mode: str = "seasonal", today: date | None = None):
    """Erzeugt das App-Symbol (Buch-Wappen in der aktuellen Design-Palette) als QIcon zur Laufzeit."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

    p = palette_for(mode, today)
    icon = QIcon()
    for size in (16, 32, 48, 64):
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, size, size)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(p["accent_hover"]))
        grad.setColorAt(0.6, QColor(p["accent"]))
        grad.setColorAt(1.0, QColor(p["accent_pressed"]))

        inset = size * 0.04
        radius = size * 0.22
        painter.setPen(QPen(QColor(p["bg_top"]), max(1.0, size * 0.04)))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), radius, radius)

        cx = rect.center().x()
        cy = rect.center().y() + size * 0.03
        bw = size * 0.60
        bh = size * 0.44
        left_x, right_x = cx - bw / 2, cx + bw / 2
        top_y, bot_y = cy - bh / 2, cy + bh / 2
        arch = bh * 0.12

        path = QPainterPath()
        path.moveTo(cx, top_y + arch)
        path.quadTo(cx - bw * 0.25, top_y - arch * 0.4, left_x, top_y + arch * 0.4)
        path.lineTo(left_x, bot_y)
        path.quadTo(cx - bw * 0.25, bot_y - arch * 0.8, cx, bot_y + arch * 0.5)
        path.quadTo(cx + bw * 0.25, bot_y - arch * 0.8, right_x, bot_y)
        path.lineTo(right_x, top_y + arch * 0.4)
        path.quadTo(cx + bw * 0.25, top_y - arch * 0.4, cx, top_y + arch)

        painter.setPen(QPen(QColor(p["accent_pressed"]), max(1.0, size * 0.03)))
        painter.setBrush(QColor("#fffaf1"))
        painter.drawPath(path)

        painter.setPen(QPen(QColor(p["accent"]), max(1.0, size * 0.035)))
        painter.drawLine(QPointF(cx, top_y + arch), QPointF(cx, bot_y + arch * 0.4))
        painter.end()
        icon.addPixmap(QPixmap.fromImage(img))
    return icon


def apply_theme(qapp, mode: str = "seasonal", today: date | None = None) -> None:
    """Wendet das Stylesheet und das passende App-Icon auf die gesamte QApplication an."""
    qapp.setStyleSheet(stylesheet_for(mode, today))
    try:
        qapp.setWindowIcon(create_app_icon(mode, today))
    except Exception:
        pass


