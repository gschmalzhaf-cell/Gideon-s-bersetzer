"""Einstiegspunkt der GUI-Anwendung.

Beim ersten Start läuft der Assistent (Offline-Weg an erster Stelle);
danach öffnet sich das Hauptfenster.

Hinweis: PySide6 und die Fenstermdodule werden erst nach dem --version-Check
importiert, damit „--version“ auch ohne GUI-Stack (z. B. CI-Smoke-Test) läuft.
"""

from __future__ import annotations

import sys


def main() -> int:
    if "--version" in sys.argv:
        from . import __version__

        print(f"Gideon's Übersetzer {__version__}")
        return 0

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication, QMessageBox

    from .main_window import MainWindow
    from .settings import load_settings, save_settings
    from .theme import apply_theme
    from .wizard import FirstStartWizard

    settings = load_settings()

    QCoreApplication.setOrganizationName("Gideons-Uebersetzer")
    QCoreApplication.setApplicationName("Gideons-Uebersetzer")
    app = QApplication(sys.argv)
    app.setApplicationDisplayName("Gideon's Übersetzer")
    apply_theme(app, settings.theme)  # kuscheliges saisonales Design ab dem ersten Fenster
    if not settings.first_start_done:
        wizard = FirstStartWizard(settings)
        wizard.exec()
        # Auch bei Abbruch des Assistenten als abgeschlossen markieren,
        # damit er nicht bei jedem Start erneut erscheint.
        settings.first_start_done = True
        save_settings(settings)

    try:
        window = MainWindow(settings)
    except Exception as exc:
        QMessageBox.critical(None, "Startfehler", f"Das Hauptfenster konnte nicht geöffnet werden: {exc}")
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
