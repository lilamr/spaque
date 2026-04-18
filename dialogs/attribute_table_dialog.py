"""
dialogs/attribute_table_dialog.py — Standalone attribute table window

Fix v1.2.0:
  1. Paginasi 5000 baris per halaman
  2. Tambah baris untuk tabel non-spasial
  3. Save di popup window kini benar (kirim referensi diri sendiri)
  4. Peringatan jelas jika tabel tidak memiliki PK
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional, Tuple
import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QTableWidget, QHeaderView, QTableWidgetItem,
    QPushButton, QMessageBox, QCheckBox,
    QFormLayout, QLineEdit, QComboBox, QDialogButtonBox,
)
from ui.panels.attribute_table import _SmartItem
from utils.logger import get_logger

logger = get_logger("spaque.dialog.attribute_table")

PAGE_SIZE = 5000   # baris per halaman


class AttributeTableDialog(QDialog):
    closed                  = pyqtSignal(str)
    add_column_requested    = pyqtSignal(str, str)
    delete_column_requested = pyqtSignal(str)
    delete_rows_requested   = pyqtSignal(list)
    save_edits_requested    = pyqtSignal(object, dict)  # (dialog_self, edits)
    add_row_requested       = pyqtSignal(object, dict)  # (dialog_self, col->val)
    refresh_data_requested  = pyqtSignal()

    def __init__(self, layer_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Atribut Tabel — {layer_name}")
        self.setMinimumSize(700, 480)
        self.resize(900, 560)
        self._layer_name   = layer_name
        self._columns: List[str] = []
        self._all_columns: List[str] = []
        self._rows: List[list] = []
        self._all_rows: List[list] = []
        self._edits: Dict[Tuple[int, str], Any] = {}
        self._pk_col: Optional[str] = None
        self._geom_type: str = ""
        self._geom_col: str = ""
        self._is_spatial: bool = True
        self._show_geom: bool = False
        self._edit_mode: bool = False
        self._current_page: int = 0
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Toolbar ───────────────────────────────────────────────────────────
        bar = QFrame()
        bar.setFixedHeight(36)
        bar.setStyleSheet("background:#13151a;border-bottom:1px solid #2d3340;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 2, 10, 2)
        bl.setSpacing(6)

        self._count_lbl = QLabel("0 fitur")
        self._count_lbl.setStyleSheet(
            "color:#6a7590;font-size:11px;background:transparent;border:none;")

        self._pk_warning_lbl = QLabel("⚠ Tidak ada PK — edit tidak tersedia")
        self._pk_warning_lbl.setStyleSheet(
            "color:#e89020;font-size:11px;background:transparent;border:none;")
        self._pk_warning_lbl.setVisible(False)
        self._pk_warning_lbl.setToolTip(
            "Tabel ini tidak memiliki Primary Key.\n"
            "Edit atribut memerlukan PK untuk mengidentifikasi baris secara unik.\n"
            "Import ulang dengan opsi 'Buat otomatis (_gid)' untuk menambahkan PK.")

        self._edit_info_lbl = QLabel("")
        self._edit_info_lbl.setStyleSheet(
            "color:#e89020;font-size:11px;background:transparent;border:none;")

        self._cancel_btn = QPushButton("✕  Batal")
        self._cancel_btn.setObjectName("secondary")
        self._cancel_btn.setFixedHeight(26)
        self._cancel_btn.setFixedWidth(82)
        self._cancel_btn.setStyleSheet("font-size:11px;padding:2px 8px;")
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._cancel_edits)

        self._save_btn = QPushButton("💾  Simpan")
        self._save_btn.setFixedHeight(26)
        self._save_btn.setFixedWidth(90)
        self._save_btn.setStyleSheet(
            "QPushButton{background:#1e9e6a;color:#fff;border:none;"
            "border-radius:5px;font-size:11px;padding:2px 8px;font-weight:600;}"
            "QPushButton:hover{background:#22b87a;}"
            "QPushButton:disabled{background:#2d3340;color:#50586a;}")
        self._save_btn.setVisible(False)
        self._save_btn.clicked.connect(self._request_save)

        self._edit_btn = QPushButton("✏  Edit")
        self._edit_btn.setObjectName("secondary")
        self._edit_btn.setFixedHeight(26)
        self._edit_btn.setFixedWidth(72)
        self._edit_btn.setStyleSheet("font-size:11px;padding:2px 8px;")
        self._edit_btn.setVisible(False)
        self._edit_btn.clicked.connect(self._toggle_edit_mode)

        self._add_row_btn = QPushButton("➕  Baris")
        self._add_row_btn.setObjectName("secondary")
        self._add_row_btn.setFixedHeight(26)
        self._add_row_btn.setStyleSheet("font-size:11px;padding:2px 8px;")
        self._add_row_btn.setVisible(False)
        self._add_row_btn.clicked.connect(self._on_add_row)

        self._delete_row_btn = QPushButton("➖  Baris")
        self._delete_row_btn.setObjectName("secondary")
        self._delete_row_btn.setFixedHeight(26)
        self._delete_row_btn.setFixedWidth(90)
        self._delete_row_btn.setStyleSheet("font-size:11px;padding:2px 8px;color:#e85050;")
        self._delete_row_btn.setVisible(False)
        self._delete_row_btn.clicked.connect(self._delete_selected_rows)

        self._add_col_btn = QPushButton("➕  Kolom")
        self._add_col_btn.setObjectName("secondary")
        self._add_col_btn.setFixedHeight(26)
        self._add_col_btn.setStyleSheet("font-size:11px;padding:2px 8px;")
        self._add_col_btn.setVisible(False)
        self._add_col_btn.clicked.connect(self._on_add_column)

        self._delete_col_btn = QPushButton("➖  Kolom")
        self._delete_col_btn.setObjectName("secondary")
        self._delete_col_btn.setFixedHeight(26)
        self._delete_col_btn.setStyleSheet("font-size:11px;padding:2px 8px;color:#e85050;")
        self._delete_col_btn.setVisible(False)
        self._delete_col_btn.clicked.connect(self._on_delete_column)

        self._show_geom_cb = QCheckBox("Kolom Geom")
        self._show_geom_cb.setStyleSheet("color:#8a93a6;font-size:11px;")
        self._show_geom_cb.setVisible(False)
        self._show_geom_cb.stateChanged.connect(self._on_show_geom_toggled)

        close_btn = QPushButton("✕  Tutup")
        close_btn.setObjectName("secondary")
        close_btn.setFixedHeight(26)
        close_btn.setStyleSheet("font-size:11px;padding:2px 10px;")
        close_btn.clicked.connect(self.close)

        bl.addWidget(self._count_lbl)
        bl.addWidget(self._show_geom_cb)
        bl.addWidget(self._pk_warning_lbl)
        bl.addStretch()
        bl.addWidget(self._edit_info_lbl)
        bl.addWidget(self._cancel_btn)
        bl.addWidget(self._save_btn)
        bl.addWidget(self._edit_btn)
        bl.addWidget(self._add_row_btn)
        bl.addWidget(self._delete_row_btn)
        bl.addWidget(self._add_col_btn)
        bl.addWidget(self._delete_col_btn)
        bl.addWidget(close_btn)
        layout.addWidget(bar)

        # ── Edit banner ───────────────────────────────────────────────────────
        self._edit_banner = QFrame()
        self._edit_banner.setFixedHeight(26)
        self._edit_banner.setStyleSheet(
            "background:#152215;border-bottom:1px solid #1e4a1e;")
        bbl = QHBoxLayout(self._edit_banner)
        bbl.setContentsMargins(12, 0, 12, 0)
        banner_lbl = QLabel(
            "✏  Mode Edit Aktif — Double-klik sel untuk mengedit · "
            "Perubahan belum tersimpan sampai klik 💾 Simpan")
        banner_lbl.setStyleSheet(
            "color:#7adb78;font-size:10px;background:transparent;border:none;")
        bbl.addWidget(banner_lbl)
        self._edit_banner.setVisible(False)
        layout.addWidget(self._edit_banner)

        # ── Tabel ─────────────────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._table.setStyleSheet(
            "QTableWidget{background:#1a1d23;color:#c0cad8;border:none;"
            "gridline-color:#2d3340;font-size:12px;}"
            "QTableWidget::item:selected{background:#2e5bff40;}"
            "QHeaderView::section{background:#13151a;color:#8a93a6;"
            "border:none;border-bottom:1px solid #2d3340;"
            "border-right:1px solid #2d3340;padding:4px 8px;font-size:11px;}"
            "QTableWidget::item{padding:4px 8px;}")
        self._table.itemChanged.connect(self._on_cell_changed)
        layout.addWidget(self._table, 1)

        # ── Paginasi bar ──────────────────────────────────────────────────────
        page_bar = QFrame()
        page_bar.setFixedHeight(34)
        page_bar.setStyleSheet("background:#13151a;border-top:1px solid #2d3340;")
        pl = QHBoxLayout(page_bar)
        pl.setContentsMargins(12, 0, 12, 0)
        pl.setSpacing(8)

        self._prev_btn = QPushButton("◀  Sebelumnya")
        self._prev_btn.setObjectName("secondary")
        self._prev_btn.setFixedHeight(24)
        self._prev_btn.setStyleSheet("font-size:11px;padding:2px 10px;")
        self._prev_btn.clicked.connect(self._prev_page)
        self._prev_btn.setEnabled(False)

        self._page_lbl = QLabel("Hal. 1 / 1")
        self._page_lbl.setStyleSheet(
            "color:#6a7590;font-size:11px;background:transparent;border:none;")
        self._page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._next_btn = QPushButton("Berikutnya  ▶")
        self._next_btn.setObjectName("secondary")
        self._next_btn.setFixedHeight(24)
        self._next_btn.setStyleSheet("font-size:11px;padding:2px 10px;")
        self._next_btn.clicked.connect(self._next_page)
        self._next_btn.setEnabled(False)

        self._page_size_lbl = QLabel(f"  {PAGE_SIZE:,} baris / halaman")
        self._page_size_lbl.setStyleSheet(
            "color:#3d4455;font-size:10px;background:transparent;border:none;")

        pl.addWidget(self._prev_btn)
        pl.addStretch()
        pl.addWidget(self._page_lbl)
        pl.addStretch()
        pl.addWidget(self._next_btn)
        pl.addWidget(self._page_size_lbl)
        layout.addWidget(page_bar)

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def populate_table(self, columns: List[str], rows: List[list],
                       pk_col: Optional[str] = None, geom_type: str = "",
                       geom_col: str = ""):
        self._all_columns = list(columns)
        self._all_rows    = [list(r) for r in rows]
        self._pk_col      = pk_col
        self._geom_type   = geom_type.upper() if geom_type else ""
        self._geom_col    = geom_col
        self._is_spatial  = bool(geom_col)
        self._show_geom   = False
        self._edits.clear()
        self._current_page = 0

        self._show_geom_cb.setVisible(bool(geom_col))
        if geom_col:
            self._show_geom_cb.setChecked(False)

        self._apply_columns_filter()

        has_pk = bool(pk_col)
        self._edit_btn.setVisible(has_pk)
        self._pk_warning_lbl.setVisible(not has_pk)
        # _add_row_btn hanya muncul saat mode edit aktif
        self._add_row_btn.setVisible(False)

    def refresh_populate(self, columns, rows, pk_col=None, geom_type="", geom_col=""):
        """Reload data setelah DDL (add/delete column) — reset semua tombol."""
        self._edit_mode = False
        self._edits.clear()
        self.populate_table(columns, rows, pk_col, geom_type, geom_col)
        self._exit_edit_ui()

    def mark_save_done(self):
        """Dipanggil main_window setelah simpan berhasil."""
        self._edits.clear()
        self._exit_edit_ui()

    def get_pk_value(self, page_row: int):
        """Ambil nilai PK dari index baris pada halaman saat ini."""
        if not self._pk_col or not self._columns:
            return None
        try:
            pk_idx    = self._columns.index(self._pk_col)
            page_rows = self._page_rows()
            if page_row < len(page_rows):
                return page_rows[page_row][pk_idx]
        except (ValueError, IndexError):
            pass
        return None

    def get_pk_value_global(self, global_row: int):
        """Ambil nilai PK dari index baris global."""
        if not self._pk_col or not self._columns:
            return None
        try:
            pk_idx = self._columns.index(self._pk_col)
            if global_row < len(self._rows):
                return self._rows[global_row][pk_idx]
        except (ValueError, IndexError):
            pass
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Paginasi
    # ─────────────────────────────────────────────────────────────────────────

    def _total_pages(self) -> int:
        return max(1, math.ceil(len(self._rows) / PAGE_SIZE))

    def _page_rows(self) -> List[list]:
        start = self._current_page * PAGE_SIZE
        return self._rows[start: start + PAGE_SIZE]

    def _prev_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._render_current_page()

    def _next_page(self):
        if self._current_page < self._total_pages() - 1:
            self._current_page += 1
            self._render_current_page()

    def _render_current_page(self):
        self._table.blockSignals(True)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        page_rows = self._page_rows()
        self._table.setRowCount(len(page_rows))

        for r, row in enumerate(page_rows):
            for c, val in enumerate(row):
                text = "" if val is None else str(val)[:300]
                item = _SmartItem(text)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, c, item)

        self._table.blockSignals(False)
        self._table.setSortingEnabled(True)

        total_pages = self._total_pages()
        self._prev_btn.setEnabled(self._current_page > 0)
        self._next_btn.setEnabled(self._current_page < total_pages - 1)
        start_row = self._current_page * PAGE_SIZE + 1
        end_row   = min(start_row + PAGE_SIZE - 1, len(self._rows))
        self._page_lbl.setText(
            f"Hal. {self._current_page + 1} / {total_pages}"
            f"  (baris {start_row:,}–{end_row:,} dari {len(self._rows):,})"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Filter kolom
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_columns_filter(self):
        if self._show_geom:
            self._columns = list(self._all_columns)
            self._rows    = [list(r) for r in self._all_rows]
        else:
            if self._geom_col and self._geom_col in self._all_columns:
                idx = self._all_columns.index(self._geom_col)
                self._columns = [c for i, c in enumerate(self._all_columns) if i != idx]
                self._rows    = [[v for i, v in enumerate(r) if i != idx]
                                 for r in self._all_rows]
            else:
                self._columns = list(self._all_columns)
                self._rows    = [list(r) for r in self._all_rows]

        self._table.setColumnCount(len(self._columns))
        self._table.setHorizontalHeaderLabels(self._columns)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)

        self._current_page = 0
        self._render_current_page()
        self._count_lbl.setText(f"{len(self._rows):,} fitur")

    def _on_show_geom_toggled(self, state):
        self._show_geom = bool(state)
        self._apply_columns_filter()

    # ─────────────────────────────────────────────────────────────────────────
    # Edit mode
    # ─────────────────────────────────────────────────────────────────────────

    def _toggle_edit_mode(self):
        if not self._pk_col:
            QMessageBox.warning(
                self, "Tidak Bisa Edit",
                "Tabel ini tidak memiliki Primary Key (PK).\n\n"
                "Edit atribut memerlukan PK untuk mengidentifikasi baris secara unik.\n\n"
                "Cara menambahkan PK:\n"
                "  • Import ulang → pilih opsi 'Buat otomatis (_gid)'\n"
                "  • Atau jalankan SQL:\n"
                "    ALTER TABLE nama_tabel\n"
                "    ADD COLUMN _gid SERIAL PRIMARY KEY")
            return

        self._edit_mode = not self._edit_mode
        if self._edit_mode:
            self._table.setEditTriggers(
                QTableWidget.EditTrigger.DoubleClicked
                | QTableWidget.EditTrigger.EditKeyPressed)
            self._edit_btn.setText("🔒  Kunci")
            self._save_btn.setVisible(True)
            self._cancel_btn.setVisible(True)
            self._edit_banner.setVisible(True)
            self._edit_info_lbl.setText("0 perubahan")
            self._delete_row_btn.setVisible(True)
            self._add_col_btn.setVisible(True)
            self._delete_col_btn.setVisible(True)
            if not self._is_spatial:
                self._add_row_btn.setVisible(True)
        else:
            self._exit_edit_ui()

    def _exit_edit_ui(self):
        self._edit_mode = False
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._edit_btn.setText("✏  Edit")
        self._save_btn.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._edit_banner.setVisible(False)
        self._edit_info_lbl.setText("")
        self._delete_row_btn.setVisible(False)
        self._add_row_btn.setVisible(False)
        self._add_col_btn.setVisible(False)
        self._delete_col_btn.setVisible(False)

    def _cancel_edits(self):
        self._edits.clear()
        self._render_current_page()
        self._exit_edit_ui()

    def _on_cell_changed(self, item: QTableWidgetItem):
        if not self._edit_mode:
            return
        row = item.row()
        col = item.column()
        if col >= len(self._columns):
            return
        col_name   = self._columns[col]
        global_row = self._current_page * PAGE_SIZE + row
        self._edits[(global_row, col_name)] = item.text()
        self._edit_info_lbl.setText(f"{len(self._edits)} perubahan")

    def _request_save(self):
        if not self._edits:
            QMessageBox.information(
                self, "Tidak Ada Perubahan",
                "Tidak ada perubahan untuk disimpan.")
            return
        if not self._pk_col:
            QMessageBox.warning(
                self, "Tidak Bisa Simpan",
                "Tabel tidak memiliki Primary Key.\n"
                "Perubahan tidak bisa disimpan ke database.")
            return
        reply = QMessageBox.question(
            self, "Simpan Perubahan",
            f"Simpan {len(self._edits)} perubahan ke database?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            # Kirim referensi diri sendiri agar main_window tahu
            # sumber edits berasal dari dialog ini, bukan bottom panel
            self.save_edits_requested.emit(self, self._edits.copy())

    # ─────────────────────────────────────────────────────────────────────────
    # Tambah baris (non-spasial)
    # ─────────────────────────────────────────────────────────────────────────

    def _on_add_row(self):
        if self._is_spatial:
            return
        non_pk_cols = [c for c in self._columns
                       if c != self._pk_col and c != self._geom_col]
        if not non_pk_cols:
            QMessageBox.information(self, "Info", "Tidak ada kolom yang bisa diisi.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Tambah Baris Baru")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 16, 20, 16)

        title_lbl = QLabel("Tambah Baris Baru")
        title_lbl.setStyleSheet("font-size:14px;font-weight:bold;color:#e0e6f0;")
        lay.addWidget(title_lbl)

        if self._pk_col:
            pk_hint = QLabel(
                f"Kolom '{self._pk_col}' (PK) akan diisi otomatis oleh database.")
            pk_hint.setStyleSheet("color:#6a7590;font-size:10px;")
            lay.addWidget(pk_hint)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        edits: Dict[str, QLineEdit] = {}
        display_cols = non_pk_cols[:20]
        for col in display_cols:
            le = QLineEdit()
            le.setFixedHeight(28)
            le.setPlaceholderText("(kosong = NULL)")
            lbl_w = QLabel(col)
            lbl_w.setStyleSheet("color:#6a7590;font-size:11px;font-weight:600;")
            form.addRow(lbl_w, le)
            edits[col] = le

        if len(non_pk_cols) > 20:
            more_lbl = QLabel(
                f"…dan {len(non_pk_cols) - 20} kolom lainnya "
                "(bisa diisi setelah baris dibuat)")
            more_lbl.setStyleSheet("color:#4a5570;font-size:10px;")
            form.addRow("", more_lbl)

        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        row_data = {
            col: (le.text().strip() or None)
            for col, le in edits.items()
        }
        self.add_row_requested.emit(self, row_data)

    # ─────────────────────────────────────────────────────────────────────────
    # Tambah / Hapus kolom
    # ─────────────────────────────────────────────────────────────────────────

    def _on_add_column(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Tambah Kolom Baru")
        dlg.setFixedWidth(380)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 18, 20, 16)

        lbl_title = QLabel("Tambah Kolom Baru")
        lbl_title.setStyleSheet("font-size:14px;font-weight:bold;color:#e0e6f0;")
        layout.addWidget(lbl_title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        name_edit = QLineEdit()
        name_edit.setFixedHeight(32)
        name_edit.setPlaceholderText("contoh: catatan, nilai_dbh, status")

        type_cb = QComboBox()
        type_cb.setFixedHeight(32)
        DATA_TYPES = [
            ("TEXT",             "TEXT — teks bebas"),
            ("INTEGER",          "INTEGER — bilangan bulat"),
            ("DOUBLE PRECISION", "DOUBLE PRECISION — bilangan desimal"),
            ("BOOLEAN",          "BOOLEAN — true / false"),
            ("DATE",             "DATE — tanggal (YYYY-MM-DD)"),
            ("TIMESTAMP",        "TIMESTAMP — tanggal dan waktu"),
            ("NUMERIC",          "NUMERIC — angka presisi tinggi"),
            ("VARCHAR(255)",     "VARCHAR(255) — teks maks 255 karakter"),
            ("BIGINT",           "BIGINT — bilangan bulat besar"),
        ]
        for val, label in DATA_TYPES:
            type_cb.addItem(label, val)

        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet("color:#6a7590;font-size:12px;font-weight:600;")
            return l

        form.addRow(_lbl("Nama Kolom:"), name_edit)
        form.addRow(_lbl("Tipe Data:"),  type_cb)
        layout.addLayout(form)

        hint = QLabel("Nama kolom: huruf, angka, dan underscore saja.")
        hint.setStyleSheet("color:#4a5570;font-size:10px;")
        layout.addWidget(hint)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        col_name  = name_edit.text().strip()
        data_type = type_cb.currentData()

        if not col_name:
            return
        if col_name in self._columns:
            QMessageBox.warning(self, "Peringatan", f"Kolom '{col_name}' sudah ada.")
            return
        if not col_name.replace("_", "").isalnum():
            QMessageBox.warning(self, "Peringatan",
                                "Nama kolom hanya boleh huruf, angka, dan underscore.")
            return
        self.add_column_requested.emit(col_name, data_type)

    def _on_delete_column(self):
        if not self._columns:
            return
        col_names = [c for c in self._columns
                     if c != self._pk_col and c != self._geom_col]
        if not col_names:
            QMessageBox.information(self, "Info",
                                    "Tidak ada kolom yang bisa dihapus.")
            return
        from PyQt6.QtWidgets import QInputDialog
        col_to_delete, ok = QInputDialog.getItem(
            self, "Hapus Kolom", "Pilih kolom untuk dihapus:",
            col_names, 0, False)
        if ok and col_to_delete:
            reply = QMessageBox.question(
                self, "Konfirmasi",
                f"Hapus kolom '{col_to_delete}'?\nTindakan ini tidak bisa dibatalkan.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.delete_column_requested.emit(col_to_delete)

    # ─────────────────────────────────────────────────────────────────────────
    # Hapus baris
    # ─────────────────────────────────────────────────────────────────────────

    def _delete_selected_rows(self):
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "Info", "Pilih baris yang akan dihapus.")
            return
        pk_values = []
        for idx in selected:
            pk_val = self.get_pk_value(idx.row())
            if pk_val is not None:
                pk_values.append(pk_val)
        if not pk_values:
            QMessageBox.warning(self, "Peringatan",
                                "Tidak dapat menghapus: PK tidak ditemukan.")
            return
        reply = QMessageBox.question(
            self, "Konfirmasi",
            f"Hapus {len(pk_values)} baris?\nTindakan ini tidak bisa dibatalkan.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_rows_requested.emit(pk_values)

    # ─────────────────────────────────────────────────────────────────────────
    # Close
    # ─────────────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self._edit_mode and self._edits:
            reply = QMessageBox.question(
                self, "Mode Edit Aktif",
                "Ada perubahan yang belum disimpan. Batalkan dan tutup?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        self.closed.emit(self._layer_name)
        event.accept()
