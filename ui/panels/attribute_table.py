"""
ui/panels/attribute_table.py — Bottom panel: attribute table + SQL console + log

FITUR BARU:
  - Edit inline: aktifkan tombol ✏ Edit, lalu double-klik sel
  - _SmartItem: numeric sort yang benar
  - save_edits_requested signal diteruskan ke MainWindow untuk UPDATE ke DB
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QTextEdit, QPushButton, QMessageBox,
    QCheckBox,
)
from utils.logger import get_logger

logger = get_logger("spaque.ui.attribute_table")


# ── Smart sort item (numeric-aware) ──────────────────────────────────────────

class _SmartItem(QTableWidgetItem):
    """QTableWidgetItem dengan numeric sort yang benar."""
    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return float(self.text()) < float(other.text())
        except (ValueError, TypeError):
            return self.text() < other.text()


# ── Attribute Table ───────────────────────────────────────────────────────────

class AttributeTable(QWidget):
    """
    Tabel atribut dengan dukungan edit inline.

    Alur edit:
      1. User klik tombol ✏ Edit  → mode edit aktif
      2. Double-klik sel          → edit inline
      3. Klik 💾 Simpan           → emit save_edits_requested
      4. MainWindow eksekusi UPDATE ke PostGIS
      5. mark_save_done()         → reset ke mode normal
    """

    export_requested     = pyqtSignal()
    save_edits_requested = pyqtSignal(dict)  # {(row_idx, col_name): new_val}
    open_in_window       = pyqtSignal(str)   # layer_name
    add_column_requested = pyqtSignal(str, str)   # column_name, data_type
    delete_column_requested = pyqtSignal(str)  # column_name
    delete_rows_requested = pyqtSignal(list)  # [pk_values]
    add_row_requested     = pyqtSignal(dict)  # {col_name: value} — tambah baris non-spasial

    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns: List[str]                    = []
        self._all_columns: List[str]                 = []
        self._rows:    List[list]                   = []
        self._all_rows: List[list]                 = []
        self._edits:   Dict[Tuple[int, str], Any]   = {}
        self._pk_col:  Optional[str]                = None
        self._layer_name: str                        = ""
        self._geom_type: str                         = ""
        self._geom_col: str                          = ""
        self._show_geom: bool                        = False
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

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

        # Edit count / warning
        self._edit_info_lbl = QLabel("")
        self._edit_info_lbl.setStyleSheet(
            "color:#e89020;font-size:11px;background:transparent;border:none;")

        # Batal editan
        self._cancel_btn = QPushButton("✕  Batal")
        self._cancel_btn.setObjectName("secondary")
        self._cancel_btn.setFixedHeight(26)
        self._cancel_btn.setFixedWidth(82)
        self._cancel_btn.setStyleSheet("font-size:11px;padding:2px 8px;")
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._cancel_edits)

        # Simpan
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

        # Toggle edit
        self._edit_btn = QPushButton("✏  Edit")
        self._edit_btn.setObjectName("secondary")
        self._edit_btn.setFixedHeight(26)
        self._edit_btn.setFixedWidth(72)
        self._edit_btn.setStyleSheet("font-size:11px;padding:2px 8px;")
        self._edit_btn.setVisible(False)   # shown only when pk_col exists
        self._edit_btn.clicked.connect(self._on_edit_btn_clicked)

        export_btn = QPushButton("⬇  Export")
        export_btn.setObjectName("secondary")
        export_btn.setFixedHeight(26)
        export_btn.setStyleSheet("font-size:11px;padding:2px 10px;")
        export_btn.clicked.connect(self.export_requested.emit)

        window_btn = QPushButton("↗  Window")
        window_btn.setObjectName("secondary")
        window_btn.setFixedHeight(26)
        window_btn.setFixedWidth(82)
        window_btn.setStyleSheet("font-size:11px;padding:2px 10px;")
        window_btn.clicked.connect(self._on_window_clicked)

        self._show_geom_cb = QCheckBox("Tampilkan Kolom Geom")
        self._show_geom_cb.setStyleSheet(
            "color:#8a93a6;font-size:11px;")
        self._show_geom_cb.setVisible(False)
        self._show_geom_cb.stateChanged.connect(self._on_show_geom_toggled)

        # Tambah baris (hanya non-spasial + punya PK)
        self._add_row_btn = QPushButton("➕  Baris")
        self._add_row_btn.setObjectName("secondary")
        self._add_row_btn.setFixedHeight(26)
        self._add_row_btn.setStyleSheet("font-size:11px;padding:2px 8px;")
        self._add_row_btn.setVisible(False)
        self._add_row_btn.clicked.connect(self._on_add_row)

        # Delete row button (edit mode only)
        self._delete_row_btn = QPushButton("➖  Baris")
        self._delete_row_btn.setObjectName("secondary")
        self._delete_row_btn.setFixedHeight(26)
        self._delete_row_btn.setStyleSheet("font-size:11px;padding:2px 8px;color:#e85050;")
        self._delete_row_btn.setVisible(False)
        self._delete_row_btn.clicked.connect(self._delete_selected_rows)

        # Add column button (edit mode only)
        self._add_col_btn = QPushButton("➕  Kolom")
        self._add_col_btn.setObjectName("secondary")
        self._add_col_btn.setFixedHeight(26)
        self._add_col_btn.setStyleSheet("font-size:11px;padding:2px 8px;")
        self._add_col_btn.setVisible(False)
        self._add_col_btn.clicked.connect(self._on_add_column)

        # Delete column button (edit mode only)
        self._delete_col_btn = QPushButton("➖  Kolom")
        self._delete_col_btn.setObjectName("secondary")
        self._delete_col_btn.setFixedHeight(26)
        self._delete_col_btn.setStyleSheet("font-size:11px;padding:2px 8px;color:#e85050;")
        self._delete_col_btn.setVisible(False)
        self._delete_col_btn.clicked.connect(self._on_delete_column)

        bl.addWidget(self._count_lbl)
        bl.addWidget(self._show_geom_cb)
        bl.addStretch()
        bl.addWidget(self._edit_info_lbl)
        bl.addWidget(self._cancel_btn)
        bl.addWidget(self._save_btn)
        bl.addWidget(self._edit_btn)
        bl.addWidget(self._add_row_btn)
        bl.addWidget(self._delete_row_btn)
        bl.addWidget(self._add_col_btn)
        bl.addWidget(self._delete_col_btn)
        bl.addWidget(export_btn)
        bl.addWidget(window_btn)
        layout.addWidget(bar)

        # ── Edit mode banner ──────────────────────────────────────────────────
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

        # ── Table ─────────────────────────────────────────────────────────────
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
            "QTableWidget::item:selected{background:#2e5bff44;color:#ffffff;}")
        self._table.cellChanged.connect(self._on_cell_changed)
        layout.addWidget(self._table, 1)

    # ── Public API ────────────────────────────────────────────────────────────

    def populate(self, columns: List[str], rows: List,
                 pk_col: Optional[str] = None, geom_type: str = "", geom_col: str = ""):
        """
        Isi tabel. pk_col adalah kolom yang dipakai sebagai WHERE key saat UPDATE.
        geom_col adalah nama kolom geometri untuk opsi tampilkan/sembunyikan.
        """
        self._all_columns = list(columns)
        self._all_rows = [list(r) for r in rows]
        self._pk_col = pk_col
        self._geom_type = geom_type.upper() if geom_type else ""
        self._geom_col = geom_col
        self._show_geom = False
        self._edits.clear()
        # Reset semua tombol edit ke kondisi awal saat layer berganti
        if self._is_edit_mode():
            self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self._edit_btn.setText("✏  Edit")
            self._edit_banner.setVisible(False)
        self._delete_row_btn.setVisible(False)
        self._add_row_btn.setVisible(False)
        self._add_col_btn.setVisible(False)
        self._delete_col_btn.setVisible(False)
        self._save_btn.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._edit_info_lbl.setText("")
        self._table.horizontalHeader().setStyleSheet("")
        self._update_edit_ui()

        self._is_spatial = bool(geom_col)
        self._show_geom_cb.setVisible(bool(geom_col))
        if geom_col:
            self._show_geom_cb.setChecked(False)
        self._apply_columns_filter()
        # _add_row_btn hanya muncul saat mode edit aktif (seperti tombol lain)
        self._add_row_btn.setVisible(False)

    def _apply_columns_filter(self):
        """Tampilkan kolom sesuai filter show_geom."""
        if self._show_geom:
            self._columns = list(self._all_columns)
            self._rows = [list(r) for r in self._all_rows]
        else:
            if self._geom_col and self._geom_col in self._all_columns:
                idx = self._all_columns.index(self._geom_col)
                self._columns = [c for i, c in enumerate(self._all_columns) if i != idx]
                self._rows = [[v for i, v in enumerate(r) if i != idx] for r in self._all_rows]
            else:
                self._columns = list(self._all_columns)
                self._rows = [list(r) for r in self._all_rows]

        self._table.setSortingEnabled(False)
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        self._table.setColumnCount(len(self._columns))
        self._table.setHorizontalHeaderLabels(self._columns)
        self._table.setRowCount(len(self._rows))

        for r, row in enumerate(self._rows):
            for c, val in enumerate(row):
                text = "" if val is None else str(val)[:300]
                item = _SmartItem(text)
                item.setData(Qt.ItemDataRole.UserRole, val)
                if val is None:
                    item.setForeground(QColor("#4a5570"))
                self._table.setItem(r, c, item)
        self._table.blockSignals(False)
        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()
        self._count_lbl.setText(f"{len(self._rows):,} fitur")

        can_edit = self._can_edit()
        self._edit_btn.setVisible(can_edit)

    def _can_edit(self) -> bool:
        """Edit hanya tersedia jika tabel memiliki Primary Key."""
        return bool(self._pk_col)

    def clear(self):
        self._cancel_edits()
        self._table.clearContents()
        self._table.setRowCount(0)
        self._table.setColumnCount(0)
        self._columns = []
        self._all_columns = []
        self._rows = []
        self._all_rows = []
        self._pk_col = None
        self._geom_col = ""
        self._edit_btn.setVisible(False)
        self._add_row_btn.setVisible(False)
        self._show_geom_cb.setVisible(False)
        self._count_lbl.setText("0 fitur")

    def set_layer_name(self, name: str):
        """Simpan nama layer untuk dialog window."""
        self._layer_name = name

    def _on_show_geom_toggled(self, state):
        self._show_geom = bool(state)
        self._apply_columns_filter()

    def _on_window_clicked(self):
        if hasattr(self, '_layer_name') and self._layer_name:
            self.open_in_window.emit(self._layer_name)

    def _on_add_row(self):
        """Tambah baris baru untuk tabel non-spasial."""
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
            pk_hint = QLabel(f"Kolom '{self._pk_col}' (PK) diisi otomatis oleh database.")
            pk_hint.setStyleSheet("color:#6a7590;font-size:10px;")
            lay.addWidget(pk_hint)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        edits = {}
        for col in non_pk_cols[:20]:
            le = QLineEdit()
            le.setFixedHeight(28)
            le.setPlaceholderText("(kosong = NULL)")
            lbl_w = QLabel(col)
            lbl_w.setStyleSheet("color:#6a7590;font-size:11px;font-weight:600;")
            form.addRow(lbl_w, le)
            edits[col] = le

        if len(non_pk_cols) > 20:
            more = QLabel(f"…dan {len(non_pk_cols) - 20} kolom lainnya")
            more.setStyleSheet("color:#4a5570;font-size:10px;")
            form.addRow("", more)

        lay.addLayout(form)

        from PyQt6.QtWidgets import QDialogButtonBox
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        row_data = {col: (le.text().strip() or None) for col, le in edits.items()}
        self.add_row_requested.emit(row_data)

    def _on_add_column(self):
        from PyQt6.QtWidgets import QInputDialog, QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox, QLabel
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
            QMessageBox.warning(self, "Peringatan",
                                f"Kolom '{col_name}' sudah ada.")
            return
        if not col_name.replace("_", "").isalnum():
            QMessageBox.warning(self, "Peringatan",
                                "Nama kolom hanya boleh huruf, angka, dan underscore.")
            return
        self.add_column_requested.emit(col_name, data_type)

    def _on_delete_column(self):
        if not self._columns:
            return
        col_names = [c for c in self._columns if c != self._pk_col]
        if not col_names:
            QMessageBox.information(self, "Info",
                                   "Tidak ada kolom yang bisa dihapus (kecuali PK).")
            return
        from PyQt6.QtWidgets import QInputDialog
        col_to_delete, ok = QInputDialog.getItem(
            self, "Hapus Kolom",
            "Pilih kolom untuk dihapus:",
            col_names, 0, False)
        if ok and col_to_delete:
            reply = QMessageBox.question(
                self, "Konfirmasi",
                f"Hapus kolom '{col_to_delete}'?\nTindakan ini tidak bisa dibatalkan.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.delete_column_requested.emit(col_to_delete)

    def _delete_selected_rows(self):
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "Info",
                                   "Pilih baris yang akan dihapus.")
            return
        pk_values = []
        for idx in selected:
            row = idx.row()
            pk_val = self.get_pk_value(row)
            if pk_val is not None:
                pk_values.append(pk_val)
        if not pk_values:
            QMessageBox.warning(self, "Peringatan",
                              "Tidak dapat menghapus baris: PK tidak ditemukan.")
            return
        reply = QMessageBox.question(
            self, "Konfirmasi",
            f"Hapus {len(pk_values)} baris?\nTindakan ini tidak bisa dibatalkan.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_rows_requested.emit(pk_values)

    def mark_save_done(self):
        """Dipanggil MainWindow setelah UPDATE ke DB berhasil."""
        self._cancel_edits()

    def get_pk_value(self, row: int) -> Optional[Any]:
        """Return nilai PK untuk baris tertentu (dari data original)."""
        if not self._pk_col or not self._columns:
            return None
        try:
            pk_idx = self._columns.index(self._pk_col)
        except ValueError:
            return None
        item = self._table.item(row, pk_idx)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # ── Edit mode logic ───────────────────────────────────────────────────────

    def _on_edit_btn_clicked(self):
        """Klik Edit: tampilkan peringatan jika tidak ada PK."""
        if not self._pk_col:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Tidak Bisa Edit",
                "Tabel ini tidak memiliki Primary Key (PK).\n\n"
                "Edit atribut memerlukan PK untuk mengidentifikasi baris secara unik.\n\n"
                "Cara menambahkan PK:\n"
                "  • Import ulang → pilih 'Buat otomatis (_gid)'\n"
                "  • Atau jalankan SQL:\n"
                "    ALTER TABLE nama_tabel\n"
                "    ADD COLUMN _gid SERIAL PRIMARY KEY")
            return
        self._toggle_edit_mode()

    def _is_edit_mode(self) -> bool:
        return self._table.editTriggers() != QTableWidget.EditTrigger.NoEditTriggers

    def _toggle_edit_mode(self):
        if self._is_edit_mode():
            # Minta konfirmasi jika ada editan pending
            if self._edits:
                ans = QMessageBox.question(
                    self, "Keluar Mode Edit",
                    f"Ada {len(self._edits)} perubahan belum disimpan.\n"
                    "Keluar dan buang semua perubahan?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if ans != QMessageBox.StandardButton.Yes:
                    return
            self._cancel_edits()
        else:
            # Aktifkan edit
            self._table.setEditTriggers(
                QTableWidget.EditTrigger.DoubleClicked |
                QTableWidget.EditTrigger.AnyKeyPressed)
            self._edit_btn.setText("🔒  Kunci")
            self._edit_banner.setVisible(True)
            self._delete_row_btn.setVisible(True)
            self._add_col_btn.setVisible(True)
            self._delete_col_btn.setVisible(True)
            if not self._is_spatial and self._pk_col:
                self._add_row_btn.setVisible(True)
            self._table.horizontalHeader().setStyleSheet(
                "QHeaderView::section{"
                "background:#152215;color:#7adb78;"
                "font-size:10px;font-weight:700;"
                "border-bottom:1px solid #1e4a1e;padding:5px 8px;}")

    def _on_cell_changed(self, row: int, col: int):
        """Dipanggil saat isi sel berubah — hanya relevan di mode edit."""
        if not self._is_edit_mode():
            return
        item = self._table.item(row, col)
        if item is None:
            return
        col_name = self._columns[col] if col < len(self._columns) else str(col)
        new_text  = item.text()
        orig_val  = item.data(Qt.ItemDataRole.UserRole)
        orig_text = "" if orig_val is None else str(orig_val)

        key = (row, col_name)
        if new_text == orig_text:
            # Kembali ke nilai asal → hapus dari pending
            self._edits.pop(key, None)
            item.setBackground(QColor(0, 0, 0, 0))
            item.setForeground(
                QColor("#4a5570") if orig_val is None else QColor("#c0cad8"))
        else:
            # Ada perubahan → tandai
            self._edits[key] = new_text
            item.setBackground(QColor("#2a2a10"))
            item.setForeground(QColor("#fde725"))

        self._update_edit_ui()

    def _update_edit_ui(self):
        """Sinkronkan label + visibilitas tombol Simpan/Batal."""
        n = len(self._edits)
        if n:
            self._edit_info_lbl.setText(f"⚠ {n} sel diubah")
            self._save_btn.setVisible(True)
            self._cancel_btn.setVisible(True)
        else:
            self._edit_info_lbl.setText("")
            # Hanya sembunyikan jika tidak sedang edit mode
            if not self._is_edit_mode():
                self._save_btn.setVisible(False)
                self._cancel_btn.setVisible(False)

    def _request_save(self):
        if not self._edits:
            return
        self.save_edits_requested.emit(dict(self._edits))

    def _cancel_edits(self):
        """Kembalikan semua sel ke nilai asal dan exit edit mode."""
        self._edits.clear()

        # Restore warna dan teks semua sel dari data original
        self._table.blockSignals(True)
        for r, row_data in enumerate(self._rows):
            for c, val in enumerate(row_data):
                item = self._table.item(r, c)
                if item is None:
                    continue
                text = "" if val is None else str(val)[:300]
                item.setText(text)
                item.setBackground(QColor(0, 0, 0, 0))
                item.setForeground(
                    QColor("#4a5570") if val is None else QColor("#c0cad8"))
        self._table.blockSignals(False)

        # Exit edit mode
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._edit_btn.setText("✏  Edit")
        self._edit_banner.setVisible(False)
        self._delete_row_btn.setVisible(False)
        self._add_row_btn.setVisible(False)
        self._add_col_btn.setVisible(False)
        self._delete_col_btn.setVisible(False)
        self._table.horizontalHeader().setStyleSheet("")
        self._save_btn.setVisible(False)
        self._cancel_btn.setVisible(False)
        self._edit_info_lbl.setText("")


# ── SQL Console ───────────────────────────────────────────────────────────────

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
        hdr.setStyleSheet("color:#6a7590;font-size:11px;font-weight:bold;")
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
            "font-size:12px;border:1px solid #2d3340;border-radius:6px;padding:6px;")
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
        self._status.setStyleSheet(
            f"color:{'#e03c4a' if error else '#6a7590'};font-size:11px;")

    def _submit(self):
        sql = self._editor.toPlainText().strip()
        if sql:
            self.sql_submitted.emit(sql)

    def focus_editor(self):
        self._editor.setFocus()


# ── Log Panel ─────────────────────────────────────────────────────────────────

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
            "font-size:11px;border:none;padding:4px;")
        layout.addWidget(self._log)

    def append(self, level: str, msg: str):
        colors = {
            "DEBUG": "#4a5570", "INFO": "#a0aab8",
            "WARNING": "#e89020", "ERROR": "#e03c4a", "CRITICAL": "#ff4a4a",
        }
        color = colors.get(level, "#a0aab8")
        safe  = msg.replace("<", "&lt;").replace(">", "&gt;")
        self._log.append(f'<span style="color:{color};">{safe}</span>')
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear(self):
        self._log.clear()


# ── Bottom Panel ──────────────────────────────────────────────────────────────

class BottomPanel(QWidget):
    """
    Tabbed bottom panel:
    - 📋 Atribut   — dengan edit inline
    - ⌨ SQL Console
    - 📜 Log
    """

    sql_submitted        = pyqtSignal(str)
    export_requested     = pyqtSignal()
    save_edits_requested = pyqtSignal(dict)
    add_row_requested     = pyqtSignal(dict)  # forwarded from attr_table

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
            QTabBar::tab:hover    {background:#2d3340;color:#c0cad8;}
        """)

        self.attr_table  = AttributeTable()
        self.sql_console = SQLConsole()
        self.log_panel   = LogPanel()

        self.attr_table.export_requested.connect(self.export_requested.emit)
        self.attr_table.save_edits_requested.connect(self.save_edits_requested.emit)
        self.attr_table.add_row_requested.connect(self.add_row_requested.emit)
        self.sql_console.sql_submitted.connect(self.sql_submitted.emit)

        self._tabs.addTab(self.attr_table,  "📋  Atribut")
        self._tabs.addTab(self.sql_console, "⌨  SQL Console")
        self._tabs.addTab(self.log_panel,   "📜  Log")

        layout.addWidget(self._tabs)

    def populate_table(self, columns: List[str], rows: List,
                       pk_col: Optional[str] = None, geom_type: str = "", geom_col: str = ""):
        self.attr_table.populate(columns, rows, pk_col, geom_type, geom_col)
        self._tabs.setCurrentIndex(0)

    def show_sql_console(self):
        self._tabs.setCurrentIndex(1)
        self.sql_console.focus_editor()

    def log(self, level: str, msg: str):
        self.log_panel.append(level, msg)
