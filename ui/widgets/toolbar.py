"""
ui/widgets/toolbar.py — Main application toolbar
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, QSize
from PyQt6.QtWidgets import QToolBar, QPushButton, QFrame, QLabel


class MainToolbar(QToolBar):
    """
    Main toolbar with action buttons.
    Emits specific signals instead of QAction triggers
    to keep the toolbar decoupled from business logic.
    """

    connect_clicked       = pyqtSignal()
    refresh_clicked       = pyqtSignal()
    query_builder_clicked = pyqtSignal()
    geoprocess_clicked    = pyqtSignal()
    sql_console_clicked   = pyqtSignal()
    import_clicked        = pyqtSignal()   # ← NEW
    export_clicked        = pyqtSignal()

    # Quick geoprocess shortcuts
    buffer_clicked        = pyqtSignal()
    intersect_clicked     = pyqtSignal()
    clip_clicked          = pyqtSignal()
    union_clicked         = pyqtSignal()
    centroid_clicked      = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(False)
        self.setIconSize(QSize(16, 16))
        self.setStyleSheet(
            "QToolBar{background:#13151a;border-bottom:1px solid #2d3340;"
            "padding:3px 8px;spacing:3px;}"
        )
        self._build()

    def _build(self):
        def btn(label: str, signal, tip: str = "", style: str = "default"):
            b = QPushButton(label)
            b.setFixedHeight(30)
            colors = {
                "primary": "#2e5bff",
                "success": "#1e9e6a",
                "default": "#1e2229",
            }
            bg = colors.get(style, "#1e2229")
            b.setStyleSheet(f"""
                QPushButton {{
                    background:{bg};color:#c0cad8;
                    border:1px solid #2d3340;border-radius:5px;
                    padding:3px 12px;font-size:12px;
                }}
                QPushButton:hover {{background:#2d3340;color:#fff;}}
                QPushButton:pressed {{background:#3d4455;}}
            """)
            if tip:
                b.setToolTip(tip)
            b.clicked.connect(signal.emit)
            self.addWidget(b)
            return b

        def sep():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setStyleSheet("background:#2d3340;max-width:1px;margin:4px 4px;")
            self.addWidget(line)

        btn("🔌  Koneksi",    self.connect_clicked,  "Hubungkan ke PostGIS  (Ctrl+Shift+C)", "primary")
        btn("🔄  Refresh",    self.refresh_clicked,  "Refresh layer  (F5)")
        sep()
        btn("📂  Import",     self.import_clicked,   "Import file spasial ke PostGIS  (Ctrl+I)", "success")
        btn("🔍  Query Builder", self.query_builder_clicked, "Visual Query Builder  (Ctrl+Q)", "success")
        btn("⚙  Geoprocessing",  self.geoprocess_clicked,   "Buka Geoprocessing Tools  (Ctrl+G)", "success")
        btn("⌨  SQL Console",    self.sql_console_clicked,  "Buka SQL Console  (Ctrl+Shift+Q)")
        sep()
        btn("⭕ Buffer",    self.buffer_clicked,    "Buffer")
        btn("⊗ Intersect",  self.intersect_clicked, "Intersect")
        btn("✂ Clip",       self.clip_clicked,      "Clip")
        btn("⊕ Union",      self.union_clicked,     "Union")
        btn("⊙ Centroid",   self.centroid_clicked,  "Centroid")
        sep()
        btn("⬇  Export",    self.export_clicked,    "Export data")
