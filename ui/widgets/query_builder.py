"""
ui/widgets/query_builder.py — Visual WHERE clause builder widget
dengan dropdown nilai otomatis dari database.
"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QComboBox, QPushButton,
    QScrollArea,
)

from core.domain.entities.layer import LayerColumn
from core.domain.value_objects import WhereCondition
from utils.constants import QUERY_OPERATORS


# ── Worker: fetch distinct values dari DB ─────────────────────────────────────

class _DistinctValuesWorker(QThread):
    done = pyqtSignal(list)

    def __init__(self, db, schema: str, table: str, column: str):
        super().__init__()
        self._db     = db
        self._schema = schema
        self._table  = table
        self._column = column

    def run(self):
        try:
            cur = self._db.cursor()
            cur.execute(
                f'SELECT DISTINCT "{self._column}" '
                f'FROM "{self._schema}"."{self._table}" '
                f'WHERE "{self._column}" IS NOT NULL '
                f'ORDER BY "{self._column}" '
                f'LIMIT 200'
            )
            rows = cur.fetchall()
            cur.close()
            values = [str(r[0]) for r in rows if r[0] is not None]
            self.done.emit(values)
        except Exception:
            self.done.emit([])


_OP_HINTS = {
    "=": "nilai", "≠": "nilai",
    ">": "angka", "≥": "angka", "<": "angka", "≤": "angka",
    "LIKE": "% wildcard %", "NOT LIKE": "% wildcard %",
    "ILIKE": "% wildcard %", "NOT ILIKE": "% wildcard %",
    "IS NULL": "", "IS NOT NULL": "",
    "IN": "'A','B'", "NOT IN": "'A','B'",
    "BETWEEN": "min, max", "NOT BETWEEN": "min, max",
}


class ConditionRow(QFrame):
    removed        = pyqtSignal(object)
    column_changed = pyqtSignal(object, str)

    def __init__(self, index: int, columns: List[LayerColumn], parent=None):
        super().__init__(parent)
        self.index    = index
        self._columns = columns
        self.setFixedHeight(44)
        self.setStyleSheet(
            "QFrame{background:#1e2229;border:1px solid #2d3340;border-radius:6px;}"
        )
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self.logic_cb = QComboBox()
        self.logic_cb.addItems(["AND", "OR", "AND NOT", "OR NOT"])
        self.logic_cb.setFixedWidth(90)
        self.logic_cb.setFixedHeight(30)
        self.logic_cb.setVisible(self.index > 0)
        layout.addWidget(self.logic_cb)

        self.col_cb = QComboBox()
        self.col_cb.setFixedHeight(30)
        self.col_cb.setMinimumWidth(150)
        for col in self._columns:
            self.col_cb.addItem(col.name)
        self.col_cb.currentTextChanged.connect(self._on_col_changed)
        layout.addWidget(self.col_cb)

        self.op_cb = QComboBox()
        self.op_cb.addItems(list(QUERY_OPERATORS.keys()))
        self.op_cb.setFixedWidth(130)
        self.op_cb.setFixedHeight(30)
        self.op_cb.currentTextChanged.connect(self._on_op_changed)
        layout.addWidget(self.op_cb)

        # Editable combobox — dropdown distinct values + free-type
        self.val_cb = QComboBox()
        self.val_cb.setEditable(True)
        self.val_cb.setFixedHeight(30)
        self.val_cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.val_cb.lineEdit().setPlaceholderText("nilai…")
        self.val_cb.setStyleSheet(
            "QComboBox{background:#13151a;border:1px solid #2d3340;"
            "border-radius:5px;padding:3px 8px;color:#e0e6f0;}"
            "QComboBox:focus{border-color:#2e5bff;}"
            "QComboBox QAbstractItemView{background:#1e2229;color:#c0cad8;"
            "border:1px solid #2d3340;selection-background-color:#2e5bff44;}"
        )
        # Autocomplete saat mengetik
        from PyQt6.QtWidgets import QCompleter
        from PyQt6.QtCore import Qt as _Qt
        self._completer = QCompleter([])
        self._completer.setCaseSensitivity(_Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(_Qt.MatchFlag.MatchContains)
        self.val_cb.setCompleter(self._completer)
        layout.addWidget(self.val_cb, 1)

        rm = QPushButton("✕")
        rm.setFixedSize(28, 28)
        rm.setStyleSheet(
            "QPushButton{background:#2d1a1a;color:#e03c4a;"
            "border:1px solid #4d2020;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#e03c4a;color:#fff;}"
        )
        rm.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(rm)

    def _on_col_changed(self, col_name: str):
        self.val_cb.clear()
        self.val_cb.lineEdit().setPlaceholderText("nilai…")
        self.column_changed.emit(self, col_name)

    def _on_op_changed(self, op: str):
        no_val = op in ("IS NULL", "IS NOT NULL")
        self.val_cb.setEnabled(not no_val)
        self.val_cb.lineEdit().setPlaceholderText(_OP_HINTS.get(op, "nilai…"))
        if no_val:
            self.val_cb.lineEdit().clear()

    def set_distinct_values(self, values: List[str]):
        current = self.val_cb.currentText()
        self.val_cb.blockSignals(True)
        self.val_cb.clear()
        self.val_cb.addItems(values)
        if current:
            self.val_cb.setCurrentText(current)
        self.val_cb.blockSignals(False)
        # Update autocomplete model
        from PyQt6.QtCore import QStringListModel
        self._completer.setModel(QStringListModel(values))

    def set_columns(self, columns: List[LayerColumn]):
        current = self.col_cb.currentText()
        self.col_cb.blockSignals(True)
        self.col_cb.clear()
        for col in columns:
            self.col_cb.addItem(col.name)
        if current in [c.name for c in columns]:
            self.col_cb.setCurrentText(current)
        self.col_cb.blockSignals(False)
        self._columns = columns

    def to_condition(self) -> WhereCondition:
        return WhereCondition(
            column=self.col_cb.currentText(),
            operator=self.op_cb.currentText(),
            value=self.val_cb.currentText().strip(),
            logic=self.logic_cb.currentText(),
        )

    @property
    def current_column(self) -> str:
        return self.col_cb.currentText()


class QueryBuilderWidget(QWidget):
    conditions_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns: List[LayerColumn] = []
        self._rows: List[ConditionRow]   = []
        self._db      = None
        self._schema  = ""
        self._table   = ""
        self._workers = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(210)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._container = QWidget()
        self._c_layout  = QVBoxLayout(self._container)
        self._c_layout.setSpacing(4)
        self._c_layout.setContentsMargins(0, 0, 0, 0)
        self._c_layout.addStretch()
        scroll.setWidget(self._container)
        layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("＋  Tambah Kondisi")
        add_btn.setObjectName("secondary")
        add_btn.setFixedHeight(30)
        add_btn.clicked.connect(self.add_condition)
        clr_btn = QPushButton("🗑  Reset")
        clr_btn.setObjectName("secondary")
        clr_btn.setFixedHeight(30)
        clr_btn.clicked.connect(self.clear)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(clr_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def set_db_context(self, db, schema: str, table: str):
        self._db     = db
        self._schema = schema
        self._table  = table

    def set_columns(self, columns: List[LayerColumn]):
        self._columns = columns
        for row in self._rows:
            row.set_columns(columns)

    def add_condition(self):
        if not self._columns:
            return
        idx = len(self._rows)
        row = ConditionRow(idx, self._columns)
        row.removed.connect(self._remove_row)
        row.column_changed.connect(self._fetch_distinct)
        self._rows.append(row)
        self._c_layout.insertWidget(self._c_layout.count() - 1, row)
        self._fetch_distinct(row, row.current_column)
        self.conditions_changed.emit()

    def clear(self):
        for row in self._rows[:]:
            row.setParent(None)
        self._rows.clear()
        self.conditions_changed.emit()

    def get_conditions(self) -> List[WhereCondition]:
        return [row.to_condition() for row in self._rows]

    def _fetch_distinct(self, row: ConditionRow, col_name: str):
        if not self._db or not self._schema or not self._table or not col_name:
            return
        w = _DistinctValuesWorker(self._db, self._schema, self._table, col_name)
        w.done.connect(lambda vals, r=row: r.set_distinct_values(vals))
        w.start()
        self._workers.append(w)

    def _remove_row(self, row: ConditionRow):
        self._rows.remove(row)
        row.setParent(None)
        for i, r in enumerate(self._rows):
            r.index = i
            r.logic_cb.setVisible(i > 0)
        self.conditions_changed.emit()
