"""
ui/panels/attribute_table.py — Bottom panel: attribute table + SQL console + log
"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QTextEdit, QPushButton,
)

from utils.logger import get_logger

logger = get_logger("spaque.ui.attribute_table")


class AttributeTable(QWidget):
    """Attribute table tab — shows feature rows."""

    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        bar = QFrame()
        bar.setFixedHeight(34)
        bar.setStyleSheet(
            "background:#13151a;border-bottom:1px solid #2d3340;"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 2, 10, 2)
        self._count_lbl = QLabel("0 fitur")
        self._count_lbl.setStyleSheet(
            "color:#6a7590;font-size:11px;background:transparent;border:none;"
        )
        export_btn = QPushButton("⬇  Export")
        export_btn.setObjectName("secondary")
        export_btn.setFixedHeight(26)
        export_btn.setStyleSheet("font-size:11px;padding:2px 10px;")
        export_btn.clicked.connect(self.export_requested.emit)
        bl.addWidget(self._count_lbl)
        bl.addStretch()
        bl.addWidget(export_btn)
        layout.addWidget(bar)

        # Table
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._table.setStyleSheet(
            "QTableWidget{border:none;font-size:11px;}"
            "QTableWidget::item{padding:3px 6px;}"
        )
        layout.addWidget(self._table, 1)

    def populate(self, columns: List[str], rows: List):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                text = "" if val is None else str(val)[:300]
                item = QTableWidgetItem(text)
                if val is None:
                    item.setForeground(QColor("#4a5570"))
                self._table.setItem(r, c, item)

        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()
        self._count_lbl.setText(f"{len(rows):,} fitur")

    def clear(self):
        self._table.clearContents()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._count_lbl.setText("0 fitur")


class SQLConsole(QWidget):
    """SQL console tab — free-form SQL entry."""

    sql_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(8)

        hdr = QLabel("Konsol SQL  —  Query bebas ke PostGIS")
        hdr.setStyleSheet(
            "color:#6a7590;font-size:11px;font-weight:bold;"
        )
        layout.addWidget(hdr)

        self._editor = QTextEdit()
        self._editor.setPlaceholderText(
            "Contoh:\n"
            "SELECT *, ST_Area(ST_Transform(geom, 32748)) / 10000 AS luas_ha\n"
            "FROM public.kawasan_hutan\n"
            "WHERE luas_ha > 100\n"
            "ORDER BY luas_ha DESC\n"
            "LIMIT 500"
        )
        self._editor.setFixedHeight(100)
        self._editor.setStyleSheet(
            "background:#0f1116;color:#7adb78;font-family:monospace;"
            "font-size:12px;border:1px solid #2d3340;border-radius:6px;"
            "padding:6px;"
        )
        layout.addWidget(self._editor)

        btn_row = QHBoxLayout()
        run_btn = QPushButton("▶  Jalankan SQL")
        run_btn.setFixedHeight(34)
        run_btn.clicked.connect(self._submit)
        clear_btn = QPushButton("🗑  Bersihkan")
        clear_btn.setObjectName("secondary")
        clear_btn.setFixedHeight(34)
        clear_btn.clicked.connect(self._editor.clear)
        btn_row.addWidget(run_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#6a7590;font-size:11px;")
        layout.addWidget(self._status)
        layout.addStretch()

    def set_status(self, msg: str, error: bool = False):
        self._status.setText(msg)
        color = "#e03c4a" if error else "#6a7590"
        self._status.setStyleSheet(f"color:{color};font-size:11px;")

    def _submit(self):
        sql = self._editor.toPlainText().strip()
        if sql:
            self.sql_submitted.emit(sql)

    def focus_editor(self):
        self._editor.setFocus()


class LogPanel(QWidget):
    """Log tab — activity log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "background:#0f1116;color:#a0aab8;font-family:monospace;"
            "font-size:11px;border:none;padding:4px;"
        )
        layout.addWidget(self._log)

    def append(self, level: str, msg: str):
        colors = {
            "DEBUG": "#4a5570",
            "INFO": "#a0aab8",
            "WARNING": "#e89020",
            "ERROR": "#e03c4a",
            "CRITICAL": "#ff4a4a",
        }
        color = colors.get(level, "#a0aab8")
        safe = msg.replace("<", "&lt;").replace(">", "&gt;")
        self._log.append(
            f'<span style="color:{color};">{safe}</span>'
        )
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear(self):
        self._log.clear()


class BottomPanel(QWidget):
    """
    Tabbed bottom panel containing:
    - Attribute Table
    - SQL Console
    - Activity Log
    """

    sql_submitted    = pyqtSignal(str)
    export_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("""
            QTabWidget::pane {border:none;background:#1a1d23;}
            QTabBar::tab {
                padding:6px 16px;font-size:11px;
                background:#13151a;color:#6a7590;
                border:1px solid #2d3340;margin-right:2px;
                border-radius:6px 6px 0 0;
            }
            QTabBar::tab:selected {background:#1a1d23;color:#e0e6f0;border-bottom-color:#1a1d23;}
            QTabBar::tab:hover {background:#2d3340;color:#c0cad8;}
        """)

        self.attr_table  = AttributeTable()
        self.sql_console = SQLConsole()
        self.log_panel   = LogPanel()

        self.attr_table.export_requested.connect(self.export_requested.emit)
        self.sql_console.sql_submitted.connect(self.sql_submitted.emit)

        self._tabs.addTab(self.attr_table,  "📋  Atribut")
        self._tabs.addTab(self.sql_console, "⌨  SQL Console")
        self._tabs.addTab(self.log_panel,   "📜  Log")

        layout.addWidget(self._tabs)

    def populate_table(self, columns: List[str], rows: List):
        self.attr_table.populate(columns, rows)
        self._tabs.setCurrentIndex(0)

    def show_sql_console(self):
        self._tabs.setCurrentIndex(1)
        self.sql_console.focus_editor()

    def log(self, level: str, msg: str):
        self.log_panel.append(level, msg)
