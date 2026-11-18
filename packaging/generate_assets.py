"""Erzeugt die grafischen Assets für App und Inno-Setup-Installer im kuscheligen Design.

Wird vor dem Windows-Build (oder beim Erneuern der Paket-Assets) ausgeführt und
schreibt deterministische Dateien nach `packaging/`:
  - `app_icon.ico` (Multi-Size-ICO: 16, 32, 48, 64, 256 px – Buch + Übersetzungspfeil in warmer Kastanien-/Gold-Palette)
  - `wizard_banner.bmp` (164x314 px, 24-Bit-BMP – Seitenbanner für Inno Setup)
  - `wizard_small.bmp` (55x58 px, 24-Bit-BMP – Kopfbild oben rechts für Inno Setup)

Nutzt PySide6 (QPainter/QImage) zum Zeichnen und verpackt das Multi-Size-ICO direkt
mit der Python-Standardbibliothek (`struct`), sodass keine Zusatzabhängigkeit wie Pillow nötig ist.
"""

from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

PACKAGING_DIR = Path(__file__).resolve().parent


def draw_book_badge(painter: QPainter, rect: QRectF) -> None:
    """Zeichnet das App-Symbol (abgerundetes Kastanien-Wappen mit offenem Buch und EN→DE-Bogen)."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Hintergrund-Wappen (warmer Herbst-/Kastanien-Verlauf)
    bg_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    bg_grad.setColorAt(0.0, QColor("#d07a2e"))
    bg_grad.setColorAt(0.55, QColor("#b5651d"))
    bg_grad.setColorAt(1.0, QColor("#7a3e0d"))

    radius = rect.width() * 0.22
    painter.setPen(QPen(QColor("#f7ead6"), max(1.0, rect.width() * 0.04)))
    painter.setBrush(bg_grad)
    inset = rect.width() * 0.04
    badge_rect = rect.adjusted(inset, inset, -inset, -inset)
    painter.drawRoundedRect(badge_rect, radius, radius)

    # Offenes Buch in der Mitte (warmes Creme)
    cx = rect.center().x()
    cy = rect.center().y() + rect.height() * 0.03
    bw = rect.width() * 0.62
    bh = rect.height() * 0.46
    left_x = cx - bw / 2
    right_x = cx + bw / 2
    top_y = cy - bh / 2
    bot_y = cy + bh / 2
    arch = bh * 0.12

    page_path = QPainterPath()
    # Linke Buchseite
    page_path.moveTo(cx, top_y + arch)
    page_path.quadTo(cx - bw * 0.25, top_y - arch * 0.4, left_x, top_y + arch * 0.4)
    page_path.lineTo(left_x, bot_y)
    page_path.quadTo(cx - bw * 0.25, bot_y - arch * 0.8, cx, bot_y + arch * 0.5)
    # Rechte Buchseite
    page_path.quadTo(cx + bw * 0.25, bot_y - arch * 0.8, right_x, bot_y)
    page_path.lineTo(right_x, top_y + arch * 0.4)
    page_path.quadTo(cx + bw * 0.25, top_y - arch * 0.4, cx, top_y + arch)

    painter.setPen(QPen(QColor("#5c3211"), max(1.0, rect.width() * 0.03)))
    painter.setBrush(QColor("#fffaf1"))
    painter.drawPath(page_path)

    # Buchfalz in der Mitte
    painter.setPen(QPen(QColor("#b5651d"), max(1.0, rect.width() * 0.035)))
    painter.drawLine(QPointF(cx, top_y + arch), QPointF(cx, bot_y + arch * 0.4))

    # Textzeilen-Andeutung auf den Seiten + goldener Übersetzungs-Stern/Funken oben
    if rect.width() >= 32:
        line_pen = QPen(QColor("#c99b68"), max(1.0, rect.width() * 0.028))
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(line_pen)
        for idx, frac in enumerate((0.30, 0.50, 0.70)):
            y = top_y + bh * frac
            # links
            painter.drawLine(QPointF(left_x + bw * 0.09, y), QPointF(cx - bw * 0.08, y))
            # rechts (etwas kräftiger als „übersetzter“ Text)
            r_pen = QPen(QColor("#b5651d" if idx == 0 else "#8f4f16"), max(1.0, rect.width() * 0.03))
            r_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(r_pen)
            painter.drawLine(QPointF(cx + bw * 0.08, y), QPointF(right_x - bw * 0.09, y))
            painter.setPen(line_pen)

        # Kleines Lesezeichen-Band unten rechts
        ribbon = QPainterPath()
        rx = cx + bw * 0.14
        ry = bot_y - bh * 0.05
        rw = bw * 0.11
        rh = bh * 0.26
        ribbon.moveTo(rx, ry)
        ribbon.lineTo(rx + rw, ry)
        ribbon.lineTo(rx + rw, ry + rh)
        ribbon.lineTo(rx + rw * 0.5, ry + rh * 0.75)
        ribbon.lineTo(rx, ry + rh)
        ribbon.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#c7462b"))
        painter.drawPath(ribbon)


def render_icon_image(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    painter = QPainter(img)
    draw_book_badge(painter, QRectF(0, 0, size, size))
    painter.end()
    return img


def build_ico_bytes(sizes: tuple[int, ...] = (16, 32, 48, 64, 256)) -> bytes:
    """Baut eine gültige Windows-.ico-Datei mit PNG-kodierten Einträgen für alle Größen."""
    png_blobs: list[bytes] = []
    for sz in sizes:
        img = render_icon_image(sz)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        png_blobs.append(bytes(ba))

    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    directory = bytearray()
    for sz, blob in zip(sizes, png_blobs):
        w_byte = 0 if sz >= 256 else sz
        h_byte = 0 if sz >= 256 else sz
        directory += struct.pack(
            "<BBBBHHII",
            w_byte,
            h_byte,
            0,      # Farbpalette
            0,      # reserviert
            1,      # Farbebenen
            32,     # Bits pro Pixel
            len(blob),
            offset,
        )
        offset += len(blob)

    return header + bytes(directory) + b"".join(png_blobs)


def generate_wizard_banner(dest: Path) -> Path:
    """Erzeugt das große Seitenbanner (164x314, 24-Bit-BMP) für Inno Setup im kuscheligen Design."""
    w, h = 164, 314
    img = QImage(w, h, QImage.Format.Format_RGB888)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Warmer Creme-/Amber-Verlauf passend zu theme.py
    grad = QLinearGradient(0, 0, 0, h)
    grad.setColorAt(0.0, QColor("#f7ead6"))
    grad.setColorAt(0.65, QColor("#eed3b0"))
    grad.setColorAt(1.0, QColor("#e3be8e"))
    painter.fillRect(0, 0, w, h, grad)

    # Dekorative warme Kreise im Hintergrund
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(181, 101, 29, 24))
    painter.drawEllipse(QPointF(w * 0.85, h * 0.15), 70, 70)
    painter.setBrush(QColor(181, 101, 29, 32))
    painter.drawEllipse(QPointF(w * 0.15, h * 0.88), 85, 85)

    # Feiner Rahmen innen
    painter.setPen(QPen(QColor("#d9c0a0"), 1.5))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(8, 8, w - 16, h - 16), 10, 10)

    # Buch-Wappen im oberen Drittel
    badge_size = 92
    draw_book_badge(painter, QRectF((w - badge_size) / 2, 34, badge_size, badge_size))

    # Titel & Untertitel im Banner
    painter.setPen(QColor("#4a3423"))
    f_title = QFont("DejaVu Sans", 11, QFont.Weight.Bold)
    painter.setFont(f_title)
    painter.drawText(QRectF(12, 140, w - 24, 44), Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap, "Gideon's\nÜbersetzer")

    painter.setPen(QColor("#7c5e44"))
    f_sub = QFont("DejaVu Sans", 8)
    painter.setFont(f_sub)
    painter.drawText(
        QRectF(14, 192, w - 28, 60),
        Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap,
        "Englische Bücher\nlokal ins Deutsche\nübersetzen → EPUB",
    )

    # Offline-Pill unten im Banner
    pill_rect = QRectF(14, h - 50, w - 28, 26)
    painter.setPen(QPen(QColor("#b5651d"), 1.0))
    painter.setBrush(QColor("#fffaf1"))
    painter.drawRoundedRect(pill_rect, 11, 11)
    painter.setPen(QColor("#b5651d"))
    f_pill = QFont("DejaVu Sans", 7, QFont.Weight.Bold)
    painter.setFont(f_pill)
    painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, "100 % Lokal & Privat")

    painter.end()
    img.save(str(dest), "BMP")
    return dest


def generate_wizard_small(dest: Path) -> Path:
    """Erzeugt das kleine Kopfbild (55x58, 24-Bit-BMP) oben rechts im Inno-Setup-Assistenten."""
    w, h = 55, 58
    img = QImage(w, h, QImage.Format.Format_RGB888)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.fillRect(0, 0, w, h, QColor("#f7ead6"))
    size = 48
    draw_book_badge(painter, QRectF((w - size) / 2, (h - size) / 2, size, size))
    painter.end()
    img.save(str(dest), "BMP")
    return dest


def generate_all(target_dir: Path = PACKAGING_DIR) -> dict[str, Path]:
    import os
    from PySide6.QtGui import QGuiApplication

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _app = QGuiApplication.instance() or QGuiApplication([])
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    ico_path = target_dir / "app_icon.ico"
    ico_path.write_bytes(build_ico_bytes())
    banner_path = generate_wizard_banner(target_dir / "wizard_banner.bmp")
    small_path = generate_wizard_small(target_dir / "wizard_small.bmp")
    return {"icon": ico_path, "banner": banner_path, "small": small_path}


if __name__ == "__main__":
    paths = generate_all()
    for name, p in paths.items():
        print(f"{name}: {p} ({p.stat().st_size} Bytes)")
