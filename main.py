#!/usr/bin/env python3
"""
main.py — Spaque entry point
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.main_window import MainWindow
from ui.components.style_editor import APP_STYLESHEET
from config import AppConfig


def main():
    # Required for some Linux/Wayland setups
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

    app = QApplication(sys.argv)
    app.setApplicationName(AppConfig.APP_NAME)
    app.setApplicationVersion(AppConfig.APP_VERSION)
    app.setOrganizationName("Spaque")

    app.setFont(QFont("Segoe UI", 9))
    # Set application icon
    from pathlib import Path
    from PyQt6.QtGui import QIcon
    icon_path = Path(__file__).parent / "assets" / "icons" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
