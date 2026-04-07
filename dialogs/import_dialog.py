"""
dialogs/import_dialog.py
Full-featured spatial file import dialog.

Layout:
┌─────────────────────────────────────────────────────────┐
│  📂 Import File Spasial ke PostGIS                      │
├──────────────┬──────────────────────────────────────────┤
│              │  ① Pilih File                            │
│  FORMAT      │  ② Opsi Target (schema, table, if_exists)│
│  STEPS       │  ③ CRS / Proyeksi                        │
│  SIDEBAR     │  ④ CSV Koordinat (conditional)           │
│              │  ⑤ Preview Tabel                         │
│              │  ──────────────────────────────────       │
│              │  [Preview]  [Import]  [Batal]            │
└──────────────┴──────────────────────────────────────────┘
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QPushButton,
    QFrame, QGroupBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QProgressBar,
    QSplitter, QScrollArea, QWidget, QApplication, QTabWidget,
    QSizePolicy, QRadioButton, QButtonGroup,
)

from core.importers.base import (
    ImportSpec, ImportResult,
    FORMAT_REGISTRY, SUPPORTED_EXTENSIONS, FILE_FILTER,
    get_file_info,
)
from core.services.import_service import ImportService
from utils.constants import COMMON_SRID
from utils.logger import get_logger

logger = get_logger("spaque.dialogs.import")


# ── Worker thread ─────────────────────────────────────────────────────────────

class _PreviewWorker(QThread):
    done = pyqtSignal(object, str)   # gdf | None, info_msg

    def __init__(self, service: ImportService, spec: ImportSpec):
        super().__init__()
        self._svc  = service
        self._spec = spec

    def run(self):
        gdf, msg = self._svc.preview_file(self._spec)
        self.done.emit(gdf, msg)


class _ImportWorker(QThread):
    done = pyqtSignal(ImportResult)

    def __init__(self, service: ImportService, spec: ImportSpec):
        super().__init__()
        self._svc  = service
        self._spec = spec

    def run(self):
        result = self._svc.import_file(self._spec)
        self.done.emit(result)


# ── Main Dialog ───────────────────────────────────────────────────────────────

class ImportDialog(QDialog):
    """Import file spasial ke PostGIS."""

    import_done = pyqtSignal(ImportResult)   # emitted after successful import

    def __init__(self, import_service: ImportService, parent=None):
        super().__init__(parent)
        self._svc            = import_service
        self._file_path: Optional[Path] = None
        self._preview_gdf    = None
        self._schemas: List[str] = ["public"]

        self.setWindowTitle("Import File Spasial ke PostGIS")
        self.resize(900, 680)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self._load_schemas()
        self._build_ui()

    # ── Load schemas ──────────────────────────────────────────────────────────

    def _load_schemas(self):
        try:
            self._schemas = self._svc.get_db_schemas()
        except Exception:
            self._schemas = ["public"]

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── LEFT: step sidebar ──
        left = self._build_sidebar()
        root.addWidget(left)

        # ── RIGHT: content area ──
        right = QWidget()
        right.setStyleSheet("background:#1a1d23;")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:#1a1d23;}")
        content = QWidget()
        content.setStyleSheet("background:#1a1d23;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 20, 24, 20)
        cl.setSpacing(16)

        # Build all sections
        self._build_file_section(cl)
        self._build_target_section(cl)
        self._build_crs_section(cl)
        self._build_csv_section(cl)
        self._build_preview_section(cl)
        cl.addStretch()

        scroll.setWidget(content)
        rl.addWidget(scroll, 1)

        # Footer buttons
        rl.addWidget(self._build_footer())
        root.addWidget(right, 1)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet("background:#13151a;border-right:1px solid #2d3340;")
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        # Header
        hdr = QLabel("  IMPORT")
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(
            "color:#6a7590;font-size:10px;font-weight:bold;letter-spacing:1.5px;"
            "background:#0f1116;border-bottom:1px solid #2d3340;padding-left:14px;"
        )
        sl.addWidget(hdr)

        # Steps
        steps = [
            ("①", "Pilih File"),
            ("②", "Target Database"),
            ("③", "Sistem Koordinat"),
            ("④", "Opsi CSV"),
            ("⑤", "Preview Data"),
        ]
        self._step_labels = []
        for num, text in steps:
            row = QFrame()
            row.setFixedHeight(52)
            row.setStyleSheet("background:transparent;border:none;")
            rl2 = QHBoxLayout(row)
            rl2.setContentsMargins(14, 0, 8, 0)
            n_lbl = QLabel(num)
            n_lbl.setFixedWidth(24)
            n_lbl.setStyleSheet("color:#3d4455;font-size:16px;background:transparent;")
            t_lbl = QLabel(text)
            t_lbl.setStyleSheet(
                "color:#4a5570;font-size:11px;font-weight:600;background:transparent;"
            )
            rl2.addWidget(n_lbl)
            rl2.addWidget(t_lbl, 1)
            sl.addWidget(row)
            self._step_labels.append((row, n_lbl, t_lbl))

        sl.addStretch()

        # Format list at bottom
        fmt_lbl = QLabel("  Format didukung:")
        fmt_lbl.setStyleSheet(
            "color:#3d4455;font-size:9px;font-weight:bold;letter-spacing:0.5px;"
            "padding:8px 14px 4px;background:transparent;"
        )
        sl.addWidget(fmt_lbl)
        for fmt in FORMAT_REGISTRY:
            fl = QLabel(f"  {fmt.icon}  {fmt.label}")
            fl.setStyleSheet("color:#3d4455;font-size:10px;padding:2px 14px;background:transparent;")
            sl.addWidget(fl)

        sl.addWidget(QLabel(""))  # spacing

        return sidebar

    def _build_file_section(self, layout):
        grp = self._section("① Pilih File Spasial")
        gl = QVBoxLayout(grp)

        # Drag-drop zone / browse button row
        drop_zone = QFrame()
        drop_zone.setFixedHeight(80)
        drop_zone.setStyleSheet("""
            QFrame {
                background:#13151a;
                border:2px dashed #2d3340;
                border-radius:10px;
            }
            QFrame:hover { border-color: #2e5bff; }
        """)
        dz_layout = QHBoxLayout(drop_zone)
        dz_layout.setContentsMargins(16, 0, 16, 0)

        self._file_icon = QLabel("📂")
        self._file_icon.setStyleSheet("font-size:28px;background:transparent;border:none;")
        info_col = QVBoxLayout()
        self._file_name_lbl = QLabel("Klik Browse atau drag-drop file spasial di sini")
        self._file_name_lbl.setStyleSheet(
            "color:#6a7590;font-size:12px;font-weight:600;background:transparent;border:none;"
        )
        self._file_meta_lbl = QLabel("SHP · GeoJSON · GPKG · KML · CSV · GDB · dan lainnya")
        self._file_meta_lbl.setStyleSheet(
            "color:#4a5570;font-size:10px;background:transparent;border:none;"
        )
        info_col.addWidget(self._file_name_lbl)
        info_col.addWidget(self._file_meta_lbl)

        browse_btn = QPushButton("  Browse…")
        browse_btn.setFixedHeight(34)
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(self._browse_file)

        dz_layout.addWidget(self._file_icon)
        dz_layout.addLayout(info_col, 1)
        dz_layout.addWidget(browse_btn)
        gl.addWidget(drop_zone)

        # File path display
        path_row = QHBoxLayout()
        path_lbl = QLabel("Path:")
        path_lbl.setStyleSheet("color:#6a7590;font-size:11px;min-width:36px;")
        self._file_path_edit = QLineEdit()
        self._file_path_edit.setPlaceholderText("Pilih file spasial…")
        self._file_path_edit.setFixedHeight(30)
        self._file_path_edit.setReadOnly(True)
        self._file_path_edit.setStyleSheet("font-size:11px;")
        path_row.addWidget(path_lbl)
        path_row.addWidget(self._file_path_edit, 1)
        gl.addLayout(path_row)

        layout.addWidget(grp)

    def _build_target_section(self, layout):
        grp = self._section("② Target Database")
        form = QFormLayout(grp)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._schema_cb = QComboBox()
        self._schema_cb.setFixedHeight(32)
        self._schema_cb.addItems(self._schemas)
        self._schema_cb.setEditable(True)

        self._table_edit = QLineEdit()
        self._table_edit.setPlaceholderText("Otomatis dari nama file jika kosong")
        self._table_edit.setFixedHeight(32)

        self._if_exists_bg = QButtonGroup(self)
        radio_row = QHBoxLayout()
        radio_row.setSpacing(16)
        for val, label, tip in [
            ("fail",    "Batalkan jika ada",   "Error jika tabel sudah ada"),
            ("replace", "Timpa (DROP+CREATE)", "Hapus tabel lama, buat baru"),
            ("append",  "Tambahkan baris",     "Tambah ke tabel yang ada"),
        ]:
            rb = QRadioButton(label)
            rb.setProperty("value", val)
            rb.setToolTip(tip)
            rb.setStyleSheet("color:#c0cad8;font-size:11px;spacing:5px;")
            if val == "fail":
                rb.setChecked(True)
            self._if_exists_bg.addButton(rb)
            radio_row.addWidget(rb)
        radio_row.addStretch()

        self._geom_col_edit = QLineEdit("geom")
        self._geom_col_edit.setFixedHeight(32)
        self._geom_col_edit.setFixedWidth(120)

        form.addRow(self._lbl("Schema:"), self._schema_cb)
        form.addRow(self._lbl("Nama Tabel:"), self._table_edit)
        form.addRow(self._lbl("Jika Sudah Ada:"), self._radio_widget(radio_row))
        form.addRow(self._lbl("Kolom Geometri:"), self._geom_col_edit)
        layout.addWidget(grp)

    def _build_crs_section(self, layout):
        grp = self._section("③ Sistem Koordinat (CRS / Proyeksi)")
        form = QFormLayout(grp)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Detected CRS from file
        self._detected_crs_lbl = QLabel("(belum ada file dipilih)")
        self._detected_crs_lbl.setStyleSheet("color:#6a7590;font-size:11px;")

        # Source SRID override
        src_row = QHBoxLayout()
        self._src_srid_cb = QCheckBox("Override CRS sumber:")
        self._src_srid_cb.setStyleSheet("color:#c0cad8;font-size:11px;")
        self._src_srid_spin = QSpinBox()
        self._src_srid_spin.setRange(1024, 999999)
        self._src_srid_spin.setValue(4326)
        self._src_srid_spin.setFixedWidth(90)
        self._src_srid_spin.setFixedHeight(30)
        self._src_srid_spin.setEnabled(False)
        self._src_srid_cb.toggled.connect(self._src_srid_spin.setEnabled)
        src_row.addWidget(self._src_srid_cb)
        src_row.addWidget(self._src_srid_spin)
        src_row.addStretch()

        # Reproject target
        repr_row = QHBoxLayout()
        self._repr_cb = QCheckBox("Reproject ke:")
        self._repr_cb.setStyleSheet("color:#c0cad8;font-size:11px;")
        self._repr_combo = QComboBox()
        self._repr_combo.setFixedHeight(30)
        self._repr_combo.setFixedWidth(230)
        self._repr_combo.addItems(list(COMMON_SRID.keys()))
        self._repr_combo.setEnabled(False)
        self._repr_cb.toggled.connect(self._repr_combo.setEnabled)
        repr_row.addWidget(self._repr_cb)
        repr_row.addWidget(self._repr_combo)
        repr_row.addStretch()

        form.addRow(self._lbl("Terdeteksi:"), self._detected_crs_lbl)
        form.addRow(self._lbl(""), self._hw(src_row))
        form.addRow(self._lbl(""), self._hw(repr_row))
        layout.addWidget(grp)

    def _build_csv_section(self, layout):
        self._csv_grp = self._section("④ Opsi CSV / Teks Koordinat")
        self._csv_grp.setVisible(False)
        form = QFormLayout(self._csv_grp)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._lon_col_edit  = QLineEdit()
        self._lon_col_edit.setPlaceholderText("Nama kolom Longitude / X  (auto-detect)")
        self._lon_col_edit.setFixedHeight(30)
        self._lat_col_edit  = QLineEdit()
        self._lat_col_edit.setPlaceholderText("Nama kolom Latitude / Y  (auto-detect)")
        self._lat_col_edit.setFixedHeight(30)
        self._delim_cb      = QComboBox()
        self._delim_cb.setFixedHeight(30)
        self._delim_cb.setFixedWidth(140)
        self._delim_cb.addItems([", (koma)", "; (titik koma)", "\\t (tab)", "  (spasi)"])
        self._enc_cb        = QComboBox()
        self._enc_cb.setFixedHeight(30)
        self._enc_cb.setFixedWidth(140)
        self._enc_cb.addItems(["utf-8", "utf-8-sig", "latin-1", "cp1252", "ascii"])

        form.addRow(self._lbl("Kolom Longitude:"), self._lon_col_edit)
        form.addRow(self._lbl("Kolom Latitude:"), self._lat_col_edit)
        form.addRow(self._lbl("Delimiter:"), self._delim_cb)
        form.addRow(self._lbl("Encoding:"), self._enc_cb)

        hint = QLabel("💡 CRS untuk CSV default = WGS84 (EPSG:4326). Ubah di bagian ③ jika perlu.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#6a7590;font-size:10px;padding:4px 0;")
        form.addRow("", hint)
        layout.addWidget(self._csv_grp)

    def _build_preview_section(self, layout):
        grp = self._section("⑤ Preview Data  (10 baris pertama)")
        gl = QVBoxLayout(grp)

        # Info bar
        self._preview_info = QLabel("Klik 'Preview' untuk melihat data sebelum import")
        self._preview_info.setStyleSheet("color:#6a7590;font-size:11px;")
        gl.addWidget(self._preview_info)

        # Progress bar (shown during preview/import)
        self._preview_progress = QProgressBar()
        self._preview_progress.setMaximum(0)
        self._preview_progress.setFixedHeight(4)
        self._preview_progress.setVisible(False)
        gl.addWidget(self._preview_progress)

        # Warnings area
        self._warn_lbl = QLabel("")
        self._warn_lbl.setWordWrap(True)
        self._warn_lbl.setStyleSheet(
            "color:#e89020;font-size:11px;background:#2a2010;"
            "border:1px solid #4a3010;border-radius:6px;padding:6px 10px;"
        )
        self._warn_lbl.setVisible(False)
        gl.addWidget(self._warn_lbl)

        # Table
        self._preview_table = QTableWidget()
        self._preview_table.setFixedHeight(200)
        self._preview_table.setAlternatingRowColors(True)
        self._preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._preview_table.setStyleSheet(
            "QTableWidget{border:1px solid #2d3340;border-radius:6px;font-size:11px;}"
            "QTableWidget::item{padding:3px 6px;}"
        )
        gl.addWidget(self._preview_table)
        layout.addWidget(grp)

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setFixedHeight(58)
        footer.setStyleSheet(
            "background:#13151a;border-top:1px solid #2d3340;"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 10, 20, 10)
        fl.setSpacing(8)

        self._import_progress = QProgressBar()
        self._import_progress.setMaximum(0)
        self._import_progress.setFixedHeight(4)
        self._import_progress.setFixedWidth(200)
        self._import_progress.setVisible(False)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#6a7590;font-size:11px;")

        cancel_btn = QPushButton("Tutup")
        cancel_btn.setObjectName("secondary")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.reject)

        self._preview_btn = QPushButton("👁  Preview")
        self._preview_btn.setObjectName("secondary")
        self._preview_btn.setFixedHeight(36)
        self._preview_btn.clicked.connect(self._do_preview)

        self._import_btn = QPushButton("⬆  Import ke PostGIS")
        self._import_btn.setFixedHeight(36)
        self._import_btn.setEnabled(False)
        self._import_btn.clicked.connect(self._do_import)

        fl.addWidget(self._import_progress)
        fl.addWidget(self._status_lbl, 1)
        fl.addWidget(cancel_btn)
        fl.addWidget(self._preview_btn)
        fl.addWidget(self._import_btn)
        return footer

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section(self, title: str) -> QGroupBox:
        grp = QGroupBox(title)
        grp.setStyleSheet("""
            QGroupBox {
                border:1px solid #2d3340;border-radius:8px;
                margin-top:10px;padding:12px 10px 10px;
                color:#6a7590;font-weight:700;font-size:11px;
                letter-spacing:0.3px;
            }
            QGroupBox::title {subcontrol-origin:margin;left:12px;padding:0 6px;}
        """)
        return grp

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet("color:#6a7590;font-size:12px;font-weight:600;")
        return l

    def _hw(self, layout) -> QWidget:
        """Wrap a layout in a widget."""
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        w.setLayout(layout)
        return w

    def _radio_widget(self, layout) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        w.setLayout(layout)
        return w

    # ── File browsing ─────────────────────────────────────────────────────────

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih File Spasial", "", FILE_FILTER
        )
        if path:
            self._set_file(Path(path))

    def _set_file(self, path: Path):
        self._file_path = path
        info = get_file_info(path)

        if not info["supported"]:
            QMessageBox.warning(
                self, "Format Tidak Didukung",
                f"Format '{path.suffix}' belum didukung.\n\n"
                "Format yang didukung: SHP, GeoJSON, GPKG, KML/KMZ, TAB, MIF, GML, GPX, FGB, DXF, GDB, CSV"
            )
            return

        # Update UI
        self._file_icon.setText(info["icon"])
        self._file_name_lbl.setText(path.name)
        self._file_name_lbl.setStyleSheet(
            "color:#e0e6f0;font-size:12px;font-weight:600;background:transparent;border:none;"
        )
        self._file_meta_lbl.setText(
            f"{info['format']}  ·  {info['size_mb']:.2f} MB"
        )
        self._file_path_edit.setText(str(path))

        # Auto-fill table name
        if not self._table_edit.text():
            self._table_edit.setText(
                re.sub(r"[^\w]", "_", path.stem.lower()).strip("_")
            )

        # Show/hide CSV section
        self._csv_grp.setVisible(info["is_csv"])

        # Clear preview
        self._preview_table.clearContents()
        self._preview_table.setRowCount(0)
        self._preview_info.setText("Klik 'Preview' untuk melihat data")
        self._import_btn.setEnabled(False)
        self._warn_lbl.setVisible(False)
        self._detected_crs_lbl.setText("(klik Preview untuk deteksi CRS)")

    # ── Spec building ─────────────────────────────────────────────────────────

    def _build_spec(self) -> Optional[ImportSpec]:
        if not self._file_path:
            return None

        # if_exists
        if_exists = "fail"
        for btn in self._if_exists_bg.buttons():
            if btn.isChecked():
                if_exists = btn.property("value")
                break

        # delimiter
        delim_map = {0: ",", 1: ";", 2: "\t", 3: " "}
        delim = delim_map.get(self._delim_cb.currentIndex(), ",")

        return ImportSpec(
            file_path=self._file_path,
            target_schema=self._schema_cb.currentText().strip() or "public",
            target_table=self._table_edit.text().strip(),
            if_exists=if_exists,
            lon_col=self._lon_col_edit.text().strip(),
            lat_col=self._lat_col_edit.text().strip(),
            csv_delimiter=delim,
            csv_encoding=self._enc_cb.currentText(),
            source_srid=self._src_srid_spin.value() if self._src_srid_cb.isChecked() else None,
            reproject_to=COMMON_SRID.get(self._repr_combo.currentText()) if self._repr_cb.isChecked() else None,
            geom_col_name=self._geom_col_edit.text().strip() or "geom",
        )

    # ── Preview ───────────────────────────────────────────────────────────────

    def _do_preview(self):
        spec = self._build_spec()
        if not spec:
            QMessageBox.warning(self, "Peringatan", "Pilih file terlebih dahulu!")
            return

        self._preview_progress.setVisible(True)
        self._preview_btn.setEnabled(False)
        self._status_lbl.setText("⏳ Membaca file…")
        QApplication.processEvents()

        self._preview_worker = _PreviewWorker(self._svc, spec)
        self._preview_worker.done.connect(self._on_preview_done)
        self._preview_worker.start()

    def _on_preview_done(self, gdf, msg: str):
        self._preview_progress.setVisible(False)
        self._preview_btn.setEnabled(True)

        if gdf is None:
            self._preview_info.setText(f"❌ {msg}")
            self._preview_info.setStyleSheet("color:#e03c4a;font-size:11px;")
            self._status_lbl.setText("Preview gagal")
            return

        self._preview_gdf = gdf
        self._preview_info.setText(f"✅ {msg}")
        self._preview_info.setStyleSheet("color:#1e9e6a;font-size:11px;")
        self._status_lbl.setText("Data berhasil dibaca")
        self._import_btn.setEnabled(True)

        # Update detected CRS
        if hasattr(gdf, 'crs') and gdf.crs:
            epsg = gdf.crs.to_epsg()
            crs_str = f"EPSG:{epsg}" if epsg else str(gdf.crs)
            self._detected_crs_lbl.setText(crs_str)
            self._detected_crs_lbl.setStyleSheet("color:#1e9e6a;font-size:11px;")
        else:
            self._detected_crs_lbl.setText("Tidak terdeteksi — set manual di bagian override")
            self._detected_crs_lbl.setStyleSheet("color:#e89020;font-size:11px;")

        # Populate table
        cols = list(gdf.columns)
        self._preview_table.setColumnCount(len(cols))
        self._preview_table.setHorizontalHeaderLabels(cols)
        self._preview_table.setRowCount(len(gdf))

        for r, row in enumerate(gdf.itertuples(index=False)):
            for c, val in enumerate(row):
                text = str(val)[:120] if val is not None else "NULL"
                item = QTableWidgetItem(text)
                if val is None:
                    item.setForeground(QColor("#4a5570"))
                self._preview_table.setItem(r, c, item)

        self._preview_table.resizeColumnsToContents()

    # ── Import ────────────────────────────────────────────────────────────────

    def _do_import(self):
        spec = self._build_spec()
        if not spec:
            return

        # Check if table exists
        if spec.if_exists == "fail":
            try:
                if self._svc.table_exists(spec.target_schema, spec.resolved_table):
                    ans = QMessageBox.question(
                        self, "Tabel Sudah Ada",
                        f'Tabel "{spec.target_schema}"."{spec.resolved_table}" sudah ada.\n\n'
                        "Ganti pilihan 'Jika Sudah Ada' menjadi 'Timpa' atau 'Tambahkan', "
                        "atau pilih nama tabel yang berbeda.",
                        QMessageBox.StandardButton.Ok,
                    )
                    return
            except Exception:
                pass

        self._import_btn.setEnabled(False)
        self._preview_btn.setEnabled(False)
        self._import_progress.setVisible(True)
        self._status_lbl.setText(
            f"⏳ Mengimport {self._file_path.name} → PostGIS…"
        )
        QApplication.processEvents()

        self._import_worker = _ImportWorker(self._svc, spec)
        self._import_worker.done.connect(self._on_import_done)
        self._import_worker.start()

    def _on_import_done(self, result: ImportResult):
        self._import_progress.setVisible(False)
        self._import_btn.setEnabled(True)
        self._preview_btn.setEnabled(True)

        if result.success:
            # Show warnings if any
            if result.has_warnings:
                self._warn_lbl.setText(
                    "⚠️ Peringatan:\n" + "\n".join(f"• {w}" for w in result.warnings)
                )
                self._warn_lbl.setVisible(True)

            self._status_lbl.setText(f"✅ {result.rows_imported:,} fitur berhasil diimport")

            QMessageBox.information(
                self, "Import Berhasil",
                f"✅ {result.message}\n\n"
                f"Schema  : {result.schema}\n"
                f"Tabel   : {result.table}\n"
                f"Geometri: {result.geom_type}\n"
                f"CRS     : EPSG:{result.srid}\n"
                f"Kolom   : {len(result.columns)}\n"
                f"Fitur   : {result.rows_imported:,}"
                + ("\n\nPeringatan:\n" + "\n".join(f"• {w}" for w in result.warnings)
                   if result.warnings else "")
            )
            self.import_done.emit(result)

        else:
            self._status_lbl.setText("❌ Import gagal")
            QMessageBox.critical(self, "Import Gagal", result.message)


# ── Fix missing import ────────────────────────────────────────────────────────
import re
