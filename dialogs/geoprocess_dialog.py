"""
dialogs/geoprocess_dialog.py — Visual geoprocessing dialog
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
    QCheckBox, QPushButton, QFrame, QTextEdit,
    QGroupBox, QScrollArea, QWidget,
)

from core.domain.entities.layer import LayerInfo
from core.domain.value_objects import GeoprocessSpec
from core.geoprocessing.factory import GeoprocessFactory
from utils.constants import SPATIAL_PREDICATES, JOIN_TYPES, AREA_UNITS, COMMON_SRID


class GeoprocessDialog(QDialog):
    """
    Two-panel dialog:
    Left  → operation tree (by category)
    Right → dynamic parameter form + SQL preview
    """

    spec_accepted = pyqtSignal(GeoprocessSpec)

    def __init__(self,
                 layers: List[LayerInfo],
                 get_columns,           # Callable[[LayerInfo], List[LayerColumn]]
                 initial_op: str = "",
                 parent=None):
        super().__init__(parent)
        self._layers    = layers
        self._get_cols  = get_columns
        self._current_op_name: Optional[str] = None
        self.setWindowTitle("Geoprocessing Tools")
        self.resize(780, 660)
        self._build_ui()
        if initial_op:
            self._select_op(initial_op)

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── LEFT: operation list ──
        left = QFrame()
        left.setFixedWidth(210)
        left.setStyleSheet("background:#13151a;border-right:1px solid #2d3340;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        hdr = QLabel("  OPERASI")
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            "background:#0f1116;color:#6a7590;font-size:10px;font-weight:bold;"
            "letter-spacing:1px;padding-left:12px;border-bottom:1px solid #2d3340;"
        )
        ll.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        op_container = QWidget()
        op_layout = QVBoxLayout(op_container)
        op_layout.setContentsMargins(0, 0, 0, 0)
        op_layout.setSpacing(0)

        self._op_buttons: dict[str, QPushButton] = {}
        ops_by_cat = GeoprocessFactory.flat_registry()

        for cat, ops in ops_by_cat.items():
            cat_lbl = QLabel(f"  {cat.upper()}")
            cat_lbl.setFixedHeight(26)
            cat_lbl.setStyleSheet(
                "color:#3d4a60;font-size:9px;font-weight:bold;"
                "letter-spacing:0.5px;background:#13151a;padding-left:12px;"
            )
            op_layout.addWidget(cat_lbl)
            for op in ops:
                b = QPushButton(f"  {op.icon}  {op.name}")
                b.setFixedHeight(34)
                b.setCheckable(True)
                b.setStyleSheet("""
                    QPushButton {
                        background:transparent;color:#a0aab8;border:none;
                        text-align:left;padding-left:20px;font-size:12px;
                    }
                    QPushButton:hover  {background:#1e2229;color:#fff;}
                    QPushButton:checked{
                        background:#2e5bff1a;color:#6699ff;
                        border-left:3px solid #2e5bff;
                    }
                """)
                b.clicked.connect(lambda _, n=op.name: self._select_op(n))
                self._op_buttons[op.name] = b
                op_layout.addWidget(b)

        op_layout.addStretch()
        scroll.setWidget(op_container)
        ll.addWidget(scroll)
        root.addWidget(left)

        # ── RIGHT: config ──
        right = QFrame()
        right.setStyleSheet("background:#1a1d23;")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(20, 16, 20, 16)
        rl.setSpacing(12)

        self._op_title = QLabel("← Pilih operasi dari panel kiri")
        self._op_title.setStyleSheet(
            "font-size:16px;font-weight:bold;color:#e0e6f0;"
        )
        self._op_desc = QLabel("")
        self._op_desc.setStyleSheet("font-size:12px;color:#6a7590;")
        rl.addWidget(self._op_title)
        rl.addWidget(self._op_desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:#2d3340;max-height:1px;")
        rl.addWidget(sep)

        # Params form (rebuilt per operation)
        self._params_frame = QFrame()
        self._params_layout = QFormLayout(self._params_frame)
        self._params_layout.setSpacing(10)
        self._params_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        rl.addWidget(self._params_frame)

        # Pre-create all parameter widgets
        self._init_param_widgets()

        # SQL preview
        sql_grp = QGroupBox("Preview SQL")
        sg = QVBoxLayout(sql_grp)
        self._sql_preview = QTextEdit()
        self._sql_preview.setReadOnly(True)
        self._sql_preview.setFixedHeight(110)
        self._sql_preview.setStyleSheet(
            "background:#0f1116;color:#7adb78;font-family:monospace;"
            "font-size:11px;border:1px solid #2d3340;border-radius:6px;"
        )
        sg.addWidget(self._sql_preview)
        rl.addWidget(sql_grp)

        # Output name
        out_row = QHBoxLayout()
        out_lbl = QLabel("Nama output:")
        out_lbl.setStyleSheet("color:#6a7590;font-size:12px;font-weight:600;")
        from PyQt6.QtWidgets import QLineEdit
        self._output_name = QLineEdit("hasil_geoprocess")
        self._output_name.setFixedHeight(34)
        out_row.addWidget(out_lbl)
        out_row.addWidget(self._output_name, 1)
        rl.addLayout(out_row)

        rl.addStretch()

        # Buttons
        br = QHBoxLayout()
        br.setSpacing(8)
        cancel = QPushButton("Batal")
        cancel.setObjectName("secondary")
        cancel.setFixedHeight(38)
        cancel.clicked.connect(self.reject)
        preview = QPushButton("👁  Preview SQL")
        preview.setObjectName("secondary")
        preview.setFixedHeight(38)
        preview.clicked.connect(self._update_preview)
        run = QPushButton("▶  Jalankan")
        run.setFixedHeight(38)
        run.setObjectName("success")
        run.clicked.connect(self._accept)
        br.addWidget(cancel)
        br.addStretch()
        br.addWidget(preview)
        br.addWidget(run)
        rl.addLayout(br)

        root.addWidget(right, 1)

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#6a7590;font-size:12px;font-weight:600;")
        return lbl

    # ── Param widgets ─────────────────────────────────────────────────────────

    def _init_param_widgets(self):
        """Create all possible param widgets once (shown/hidden per op)."""
        table_items = [f"{lyr.schema}.{lyr.table_name}" for lyr in self._layers]

        def combo(items=None):
            cb = QComboBox()
            cb.setFixedHeight(32)
            if items:
                cb.addItems(items)
            return cb

        self.w_input    = combo(table_items)
        self.w_overlay  = combo(table_items)
        self.w_distance = QDoubleSpinBox()
        self.w_distance.setRange(0.001, 999_999)
        self.w_distance.setValue(500)
        self.w_distance.setDecimals(3)
        self.w_distance.setFixedHeight(32)
        self.w_segments = QSpinBox()
        self.w_segments.setRange(4, 64)
        self.w_segments.setValue(16)
        self.w_segments.setFixedHeight(32)
        self.w_dissolve = QCheckBox("Gabung semua geometri hasil menjadi satu")
        self.w_dissolve.setStyleSheet("color:#c0cad8;")
        self.w_dissolve_field = combo(["(gabung semua)"])
        self.w_tolerance = QDoubleSpinBox()
        self.w_tolerance.setRange(0.000001, 100)
        self.w_tolerance.setValue(0.001)
        self.w_tolerance.setDecimals(6)
        self.w_tolerance.setFixedHeight(32)
        self.w_preserve = QCheckBox("Pertahankan topologi")
        self.w_preserve.setChecked(True)
        self.w_preserve.setStyleSheet("color:#c0cad8;")
        self.w_srid = combo(list(COMMON_SRID.keys()))
        self.w_value_col = combo(["(pilih kolom numerik)"])
        self.w_group_col = combo(["(tidak ada)"])
        self.w_area_unit = combo(list(AREA_UNITS.keys()))
        self.w_predicate = combo(SPATIAL_PREDICATES)
        self.w_join_type = combo(JOIN_TYPES)
        self.w_k = QSpinBox()
        self.w_k.setRange(1, 100)
        self.w_k.setValue(1)
        self.w_k.setFixedHeight(32)

        # Join by Field: kolom kunci dari masing-masing tabel
        self.w_left_field  = combo(["(pilih kolom)"])
        self.w_right_field = combo(["(pilih kolom)"])

        # Connect input/overlay layer change to update field combos
        self.w_input.currentIndexChanged.connect(self._refresh_field_combos)
        self.w_overlay.currentIndexChanged.connect(self._on_overlay_changed)

    def _on_overlay_changed(self):
        """Dipanggil saat pilihan overlay berubah — refresh kolom kunci kanan."""
        self._refresh_right_field()
        self._refresh_field_combos()
        self._update_preview()

    def _refresh_right_field(self):
        """Reload daftar kolom untuk w_right_field dari overlay yang dipilih saat ini."""
        ov_idx = self.w_overlay.currentIndex()
        if ov_idx < 0 or ov_idx >= len(self._layers):
            return
        try:
            ov_cols = self._get_cols(self._layers[ov_idx])
            ov_non_geom = [c.name for c in ov_cols if not c.is_geometry]
        except Exception:
            ov_non_geom = []
        cur = self.w_right_field.currentText()
        self.w_right_field.blockSignals(True)
        self.w_right_field.clear()
        self.w_right_field.addItems(["(pilih kolom)"] + ov_non_geom)
        if cur in ov_non_geom:
            self.w_right_field.setCurrentText(cur)
        self.w_right_field.blockSignals(False)

    def _refresh_field_combos(self, force_reload: bool = False):
        idx = self.w_input.currentIndex()
        if idx < 0 or idx >= len(self._layers):
            return
        layer = self._layers[idx]
        try:
            # force_reload=True bypasses cache — dipakai setelah add/delete column
            if force_reload and hasattr(self._get_cols, '__self__'):
                repo = self._get_cols.__self__._repo
                repo.invalidate_cache()
            cols = self._get_cols(layer)
            non_geom = [c.name for c in cols if not c.is_geometry]
            numeric  = [c.name for c in cols if c.is_numeric]
        except Exception:
            non_geom, numeric = [], []

        # Overlay/join layer kolom — selalu reload dari layer yang dipilih
        ov_idx = self.w_overlay.currentIndex()
        ov_non_geom = []
        if 0 <= ov_idx < len(self._layers):
            try:
                ov_layer = self._layers[ov_idx]
                ov_cols  = self._get_cols(ov_layer)
                # Untuk tabel non-spasial, semua kolom non-geom termasuk
                ov_non_geom = [c.name for c in ov_cols if not c.is_geometry]
            except Exception as e:
                ov_non_geom = []

        for cb, base, items in [
            (self.w_dissolve_field, ["(gabung semua)"], non_geom),
            (self.w_value_col,      ["(pilih kolom numerik)"], numeric),
            (self.w_group_col,      ["(tidak ada)"], non_geom),
            (self.w_left_field,     ["(pilih kolom)"], non_geom),
            (self.w_right_field,    ["(pilih kolom)"], ov_non_geom),
        ]:
            cb.blockSignals(True)
            cb.clear()
            cb.addItems(base + items)
            cb.blockSignals(False)

        self._update_preview()

    # ── Operation selection ───────────────────────────────────────────────────

    def _select_op(self, name: str):
        for n, b in self._op_buttons.items():
            b.setChecked(n == name)
        self._current_op_name = name

        op = GeoprocessFactory.get(name)
        if not op:
            return

        self._op_title.setText(f"{op.icon}  {op.name}")
        self._op_desc.setText(op.description)

        # Clear form
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        def row(label, widget):
            self._params_layout.addRow(self._lbl(label), widget)

        row("Layer Input:", self.w_input)
        if op.requires_overlay:
            row("Layer Kedua:", self.w_overlay)

        # Operation-specific params
        match name:
            case "Buffer":
                row("Jarak:", self.w_distance)
                row("Segmen busur:", self.w_segments)
                row("", self.w_dissolve)
            case "Simplify":
                row("Toleransi:", self.w_tolerance)
                row("", self.w_preserve)
            case "Dissolve" | "Union":
                self._refresh_field_combos()
                row("Gabung berdasarkan:", self.w_dissolve_field)
            case "Reproject":
                row("Target CRS:", self.w_srid)
            case "Hitung Luas":
                row("Satuan:", self.w_area_unit)
            case "Statistik Spasial":
                self._refresh_field_combos()
                row("Kolom nilai:", self.w_value_col)
                row("Kolom grup:", self.w_group_col)
            case "Select by Location" | "Spatial Join":
                row("Predikat:", self.w_predicate)
                if name == "Spatial Join":
                    row("Tipe join:", self.w_join_type)
            case "Select by Distance":
                row("Jarak (unit CRS):", self.w_distance)
            case "Nearest Neighbor":
                row("K tetangga:", self.w_k)
            case "Join by Field":
                # Tampilkan overlay picker terlebih dahulu
                row("Layer Join:", self.w_overlay)
                row("Kolom kunci Input:", self.w_left_field)
                row("Kolom kunci Join:", self.w_right_field)
                row("Tipe join:", self.w_join_type)
                # Refresh setelah widgets ada di form
                self._refresh_field_combos()

        self._update_preview()

    # ── SQL preview ───────────────────────────────────────────────────────────

    def _build_spec(self) -> Optional[GeoprocessSpec]:
        if not self._current_op_name or not self._layers:
            return None

        idx = self.w_input.currentIndex()
        if idx < 0:
            return None
        inp = self._layers[idx]

        ov_idx = self.w_overlay.currentIndex()
        ov = self._layers[ov_idx] if ov_idx >= 0 and ov_idx < len(self._layers) else None

        def field(cb):
            t = cb.currentText()
            return None if t.startswith("(") else t

        srid_label = self.w_srid.currentText()
        srid = COMMON_SRID.get(srid_label, 4326)

        return GeoprocessSpec(
            operation=self._current_op_name,
            input_schema=inp.schema,
            input_table=inp.table_name,
            input_geom=inp.geom_col,
            output_table=self._output_name.text().strip() or "hasil",
            output_schema="public",
            overlay_schema=ov.schema if ov else None,
            overlay_table=ov.table_name if ov else None,
            overlay_geom=ov.geom_col if ov else None,
            distance=self.w_distance.value(),
            tolerance=self.w_tolerance.value(),
            segments=self.w_segments.value(),
            target_srid=srid,
            dissolve_field=field(self.w_dissolve_field),
            value_col=field(self.w_value_col),
            group_col=field(self.w_group_col),
            k_neighbors=self.w_k.value(),
            spatial_predicate=self.w_predicate.currentText(),
            join_type=self.w_join_type.currentText(),
            area_unit=self.w_area_unit.currentText(),
            dissolve=self.w_dissolve.isChecked(),
            preserve_topology=self.w_preserve.isChecked(),
            join_left_field=field(self.w_left_field),
            join_right_field=field(self.w_right_field),
        )

    def _update_preview(self):
        spec = self._build_spec()
        if not spec:
            self._sql_preview.setPlainText("-- Pilih operasi dan layer")
            return
        op = GeoprocessFactory.get(spec.operation)
        if op:
            try:
                sql = op.build_sql(spec)
                self._sql_preview.setPlainText(sql)
            except Exception as exc:
                self._sql_preview.setPlainText(f"-- Error: {exc}")

    def _accept(self):
        from PyQt6.QtWidgets import QMessageBox
        spec = self._build_spec()
        if not spec:
            QMessageBox.warning(self, "Peringatan", "Pilih operasi dan layer terlebih dahulu!")
            return
        op = GeoprocessFactory.get(spec.operation)
        if op and op.requires_overlay and not spec.overlay_table:
            QMessageBox.warning(self, "Peringatan",
                                f"Operasi '{spec.operation}' memerlukan layer kedua.")
            return
        self.spec_accepted.emit(spec)
        self.accept()
