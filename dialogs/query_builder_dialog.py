"""
dialogs/query_builder_dialog.py — Visual attribute query builder dialog
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton,
    QFrame, QTextEdit, QGroupBox, QSpinBox,
    QCheckBox,
)

from core.domain.entities.layer import LayerInfo, LayerColumn
from core.domain.value_objects import QuerySpec
from ui.widgets.query_builder import QueryBuilderWidget


class QueryBuilderDialog(QDialog):
    """
    Full dialog wrapping QueryBuilderWidget.
    Emits sql_ready(sql, geom_col) on Run.
    """

    sql_ready  = pyqtSignal(str, str)        # sql, geom_col
    sql_save   = pyqtSignal(str, str, str)   # sql, geom_col, table_name

    def __init__(self,
                 layers: List[LayerInfo],
                 get_columns,           # Callable[[LayerInfo], List[LayerColumn]]
                 db=None,               # DatabaseConnection untuk distinct values
                 parent=None):
        super().__init__(parent)
        self._layers   = layers
        self._get_cols = get_columns
        self._db       = db
        self._columns: List[LayerColumn] = []
        self.setWindowTitle("Query Builder Visual")
        self.resize(780, 600)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # Title
        title = QLabel("🔍  Query Builder Visual")
        title.setStyleSheet("font-size:15px;font-weight:bold;color:#e0e6f0;")
        sub = QLabel("Bangun query atribut dengan klik-pilih tanpa menulis SQL")
        sub.setStyleSheet("font-size:11px;color:#6a7590;")
        layout.addWidget(title)
        layout.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:#2d3340;max-height:1px;")
        layout.addWidget(sep)

        # Table selector
        tbl_row = QHBoxLayout()
        tbl_lbl = QLabel("Layer / Tabel:")
        tbl_lbl.setStyleSheet("color:#6a7590;font-weight:600;font-size:12px;")
        self._table_cb = QComboBox()
        self._table_cb.setFixedHeight(34)
        self._table_cb.addItems([f"{lyr.schema}.{lyr.table_name}" for lyr in self._layers])
        self._table_cb.currentIndexChanged.connect(self._on_table_changed)
        tbl_row.addWidget(tbl_lbl)
        tbl_row.addWidget(self._table_cb, 1)
        layout.addLayout(tbl_row)

        # WHERE builder
        where_grp = QGroupBox("Kondisi Filter (WHERE)")
        wl = QVBoxLayout(where_grp)
        self._builder = QueryBuilderWidget()
        self._builder.conditions_changed.connect(self._update_preview)
        wl.addWidget(self._builder)
        layout.addWidget(where_grp)

        # ORDER + LIMIT row
        opts = QHBoxLayout()
        opts.setSpacing(12)
        ord_lbl = QLabel("Urutkan:")
        ord_lbl.setStyleSheet("color:#6a7590;font-size:12px;font-weight:600;")
        self._order_cb = QComboBox()
        self._order_cb.setFixedHeight(32)
        self._order_cb.addItem("(tidak diurutkan)")
        self._order_cb.currentIndexChanged.connect(self._update_preview)
        self._order_dir = QComboBox()
        self._order_dir.addItems(["ASC", "DESC"])
        self._order_dir.setFixedWidth(72)
        self._order_dir.setFixedHeight(32)
        self._order_dir.currentIndexChanged.connect(self._update_preview)
        lim_lbl = QLabel("Limit:")
        lim_lbl.setStyleSheet("color:#6a7590;font-size:12px;font-weight:600;")
        self._limit = QSpinBox()
        self._limit.setRange(0, 1_000_000)
        self._limit.setValue(0)
        self._limit.setSpecialValueText("semua")
        self._limit.setFixedWidth(90)
        self._limit.setFixedHeight(32)
        self._limit.valueChanged.connect(self._update_preview)
        opts.addWidget(ord_lbl)
        opts.addWidget(self._order_cb, 1)
        opts.addWidget(self._order_dir)
        opts.addWidget(lim_lbl)
        opts.addWidget(self._limit)
        layout.addLayout(opts)

        # SQL preview
        sql_grp = QGroupBox("Preview SQL")
        sg = QVBoxLayout(sql_grp)
        self._sql_view = QTextEdit()
        self._sql_view.setReadOnly(True)
        self._sql_view.setFixedHeight(100)
        self._sql_view.setStyleSheet(
            "background:#0f1116;color:#7adb78;font-family:monospace;"
            "font-size:11px;border:1px solid #2d3340;border-radius:6px;"
        )
        sg.addWidget(self._sql_view)
        layout.addWidget(sql_grp)

        # Simpan sebagai tabel (seamless workflow)
        save_frame = QFrame()
        save_frame.setStyleSheet(
            "QFrame{background:#13151a;border:1px solid #2d3340;border-radius:6px;padding:2px;}"
        )
        save_layout = QHBoxLayout(save_frame)
        save_layout.setContentsMargins(8, 4, 8, 4)
        save_layout.setSpacing(8)
        self._save_cb = QCheckBox("💾  Simpan hasil sebagai tabel PostGIS:")
        self._save_cb.setStyleSheet("color:#c0cad8;font-size:12px;")
        self._save_name = QLineEdit("hasil_query")
        self._save_name.setFixedHeight(28)
        self._save_name.setFixedWidth(180)
        self._save_name.setEnabled(False)
        self._save_cb.toggled.connect(self._save_name.setEnabled)
        save_layout.addWidget(self._save_cb)
        save_layout.addWidget(self._save_name)
        save_layout.addStretch()
        layout.addWidget(save_frame)

        # Buttons
        br = QHBoxLayout()
        br.setSpacing(8)
        cancel = QPushButton("Batal")
        cancel.setObjectName("secondary")
        cancel.setFixedHeight(38)
        cancel.clicked.connect(self.reject)
        reset = QPushButton("🗑  Reset")
        reset.setObjectName("secondary")
        reset.setFixedHeight(38)
        reset.clicked.connect(self._reset)
        run = QPushButton("▶  Jalankan Query")
        run.setFixedHeight(38)
        run.clicked.connect(self._run)
        br.addWidget(cancel)
        br.addWidget(reset)
        br.addStretch()
        br.addWidget(run)
        layout.addLayout(br)

        # Init
        if self._layers:
            self._on_table_changed(0)

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _on_table_changed(self, idx: int):
        if idx < 0 or idx >= len(self._layers):
            return
        layer = self._layers[idx]
        try:
            self._columns = self._get_cols(layer)
        except Exception:
            self._columns = []

        self._builder.set_columns(self._columns)
        # Wire DB context untuk auto-fetch distinct values
        if self._db:
            self._builder.set_db_context(self._db, layer.schema, layer.table_name)

        # Update ORDER combo
        self._order_cb.blockSignals(True)
        self._order_cb.clear()
        self._order_cb.addItem("(tidak diurutkan)")
        self._order_cb.addItems([c.name for c in self._columns])
        self._order_cb.blockSignals(False)
        self._update_preview()

    def _build_spec(self) -> Optional[QuerySpec]:
        idx = self._table_cb.currentIndex()
        if idx < 0:
            return None
        layer = self._layers[idx]
        ord_text = self._order_cb.currentText()
        lim = self._limit.value() if self._limit.value() > 0 else None
        spec = QuerySpec(
            schema=layer.schema,
            table=layer.table_name,
            conditions=self._builder.get_conditions(),
            order_col=None if ord_text.startswith("(") else ord_text,
            order_dir=self._order_dir.currentText(),
            limit=lim,
        )
        return spec

    def _update_preview(self):
        spec = self._build_spec()
        self._sql_view.setPlainText(spec.build_sql() if spec else "")

    def _reset(self):
        self._builder.clear()
        self._update_preview()

    def _run(self):
        from PyQt6.QtWidgets import QMessageBox
        spec = self._build_spec()
        if not spec:
            QMessageBox.warning(self, "Peringatan", "Pilih layer terlebih dahulu!")
            return
        idx   = self._table_cb.currentIndex()
        layer = self._layers[idx]
        sql   = spec.build_sql()
        if self._save_cb.isChecked():
            tbl = self._save_name.text().strip() or "hasil_query"
            self.sql_save.emit(sql, layer.geom_col, tbl)
        else:
            self.sql_ready.emit(sql, layer.geom_col)
        self.accept()
