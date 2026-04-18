"""
ui/main_window.py — Main application window
Wires all panels, dialogs, services, and workers together.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, List

import geopandas as gpd
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QCloseEvent
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QMessageBox, QFileDialog, QApplication,
    QProgressBar, QLabel,
)

from config import AppConfig, UIConfig
from core.database.connection import DatabaseConnection
from core.database.postgis import PostGISDatabase
from core.database.repository import LayerRepository
from core.domain.entities.layer import LayerInfo
from core.domain.value_objects import ConnectionParams, GeoprocessSpec
from core.services.layer_service import LayerService
from core.services.query_service import QueryService, QueryResult
from core.services.geoprocess_service import GeoprocessService
from core.services.import_service import ImportService
from core.exporters.base import EXPORTERS

from ui.panels.layer_browser import LayerBrowser
from ui.panels.map_canvas import MapCanvas
from ui.panels.attribute_table import BottomPanel
from ui.widgets.toolbar import MainToolbar

from dialogs.connection_dialog import ConnectionDialog
from dialogs.geoprocess_dialog import GeoprocessDialog
from dialogs.query_builder_dialog import QueryBuilderDialog
from dialogs.import_dialog import ImportDialog
from dialogs.pipeline_dialog import PipelineDialog
from dialogs.attribute_table_dialog import AttributeTableDialog
from dialogs.project_dialog import (
    ProjectPropertiesDialog, RecentProjectsDialog, ask_save_changes
)
from dialogs.help_dialog import open_help

from core.project.service import ProjectService
from core.project.model import SPQ_EXTENSION

from utils.logger import get_logger, get_qt_handler


logger = get_logger("spaque.main_window")


# ── Background worker threads ─────────────────────────────────────────────────

class QueryWorker(QThread):
    finished = pyqtSignal(QueryResult)

    def __init__(self, service: QueryService, sql: str, geom_col: Optional[str]):
        super().__init__()
        self._service  = service
        self._sql      = sql
        self._geom_col = geom_col

    def run(self):
        result = self._service.execute_sql(self._sql, self._geom_col)
        self.finished.emit(result)


class GeoWorker(QThread):
    finished = pyqtSignal(object)   # GeoprocessResult

    def __init__(self, service: GeoprocessService, spec: GeoprocessSpec):
        super().__init__()
        self._service = service
        self._spec    = spec

    def run(self):
        result = self._service.run(self._spec)
        self.finished.emit(result)


class ConnectWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, conn: DatabaseConnection, params: ConnectionParams):
        super().__init__()
        self._conn   = conn
        self._params = params

    def run(self):
        ok, msg = self._conn.connect(self._params)
        self.finished.emit(ok, msg)


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        # ── Infrastructure ────────────────────────────────────────────────────
        self._db_conn   = DatabaseConnection()
        self._postgis:  Optional[PostGISDatabase]    = None
        self._repo:     Optional[LayerRepository]    = None
        self._layer_svc: Optional[LayerService]      = None
        self._query_svc: Optional[QueryService]      = None
        self._geo_svc:  Optional[GeoprocessService]  = None
        self._import_svc: Optional[ImportService]    = None

        # ── Project management ────────────────────────────────────────────────
        self._project = ProjectService()

        self._current_gdf:   Optional[gpd.GeoDataFrame] = None
        self._current_layer: Optional[LayerInfo]         = None

        # ── Window setup ──────────────────────────────────────────────────────
        self.setWindowTitle(
            f"{AppConfig.APP_NAME} — PostGIS Desktop GIS  v{AppConfig.APP_VERSION}"
        )
        self.resize(UIConfig.DEFAULT_WIDTH, UIConfig.DEFAULT_HEIGHT)
        self.setMinimumSize(UIConfig.WINDOW_MIN_WIDTH, UIConfig.WINDOW_MIN_HEIGHT)

        self._build_ui()
        self._build_menu()
        self._connect_log_handler()

        logger.info("Spaque %s started", AppConfig.APP_VERSION)

    # ─────────────────────────────────────────────────────────────────────────
    # UI assembly
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Toolbar
        self._toolbar = MainToolbar(self)
        self.addToolBar(self._toolbar)
        self._wire_toolbar()

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Horizontal splitter: layer browser | main area
        self._h_split = QSplitter(Qt.Orientation.Horizontal)
        self._h_split.setHandleWidth(2)
        self._h_split.setStyleSheet("QSplitter::handle{background:#2d3340;}")

        # Layer browser (left)
        self._layer_browser = LayerBrowser()
        self._wire_layer_browser()
        self._h_split.addWidget(self._layer_browser)

        # Vertical splitter: map | bottom panel
        self._v_split = QSplitter(Qt.Orientation.Vertical)
        self._v_split.setHandleWidth(2)
        self._v_split.setStyleSheet("QSplitter::handle{background:#2d3340;}")

        self._map_canvas  = MapCanvas()
        self._bottom_panel = BottomPanel()
        self._wire_bottom_panel()

        self._v_split.addWidget(self._map_canvas)
        self._v_split.addWidget(self._bottom_panel)
        self._v_split.setSizes([UIConfig.DEFAULT_HEIGHT - UIConfig.BOTTOM_PANEL_HEIGHT,
                                 UIConfig.BOTTOM_PANEL_HEIGHT])

        self._h_split.addWidget(self._v_split)
        self._h_split.setSizes([UIConfig.LEFT_PANEL_WIDTH,
                                 UIConfig.DEFAULT_WIDTH - UIConfig.LEFT_PANEL_WIDTH])
        root_layout.addWidget(self._h_split)

        # Status bar
        self._build_statusbar()

    def _build_statusbar(self):
        sb = self.statusBar()
        self._progress = QProgressBar()
        self._progress.setFixedWidth(180)
        self._progress.setMaximum(0)
        self._progress.setVisible(False)
        sb.addPermanentWidget(self._progress)

        self._db_status_lbl = QLabel("  ⬤  Tidak terhubung  ")
        self._db_status_lbl.setStyleSheet("color:#e03c4a;font-size:11px;")
        sb.addPermanentWidget(self._db_status_lbl)
        sb.showMessage(f"{AppConfig.APP_NAME} siap — hubungkan ke PostGIS untuk memulai")

    def _build_menu(self):
        mb = self.menuBar()

        # Project (NEW)
        m = mb.addMenu("&Project")
        self._act(m, "📄  Baru",             self._project_new,       "Ctrl+N")
        self._act(m, "📂  Buka…",            self._project_open,      "Ctrl+O")
        self._act(m, "🕐  Buka Terakhir…",   self._project_open_recent)
        m.addSeparator()
        self._act(m, "💾  Simpan",           self._project_save,      "Ctrl+S")
        self._act(m, "💾  Simpan Sebagai…",  self._project_save_as,   "Ctrl+Shift+S")
        m.addSeparator()
        self._act(m, "⚙  Properti Project…", self._project_properties)
        m.addSeparator()
        self._recent_menu = m.addMenu("📋  File Terakhir")
        self._rebuild_recent_menu()

        # Database
        m = mb.addMenu("&Database")
        self._act(m, "🔌  Koneksi ke PostGIS…", self._open_connection, "Ctrl+Shift+C")
        self._act(m, "🔄  Refresh Layer", self._refresh_layers, "F5")
        m.addSeparator()
        self._act(m, "📂  Import File Spasial…", self._open_import, "Ctrl+I")
        m.addSeparator()
        self._act(m, "❌  Putus Koneksi", self._disconnect)

        # Layer
        m = mb.addMenu("&Layer")
        self._act(m, "🗺  Tampilkan di Peta", self._load_selected_layer)
        self._act(m, "📋  Lihat Atribut", self._view_selected_attrs)
        m.addSeparator()
        self._act(m, "📊  Statistik Layer", self._show_layer_stats)
        m.addSeparator()
        self._act(m, "🗑  Hapus Tabel dari Database", self._delete_selected_layer)

        # Query
        m = mb.addMenu("&Query")
        self._act(m, "🔍  Query Builder…", self._open_query_builder, "Ctrl+Q")
        self._act(m, "⌨  SQL Console", self._open_sql_console, "Ctrl+Shift+Q")
        m.addSeparator()
        self._act(m, "🔀  Visual Pipeline Builder…", self._open_pipeline, "Ctrl+P")

        # Geoprocessing
        m = mb.addMenu("&Geoprocessing")
        self._act(m, "⚙  Geoprocessing Tools…", self._open_geoprocess, "Ctrl+G")
        m.addSeparator()
        for op in ["Buffer", "Intersect", "Clip", "Union", "Difference",
                   "Centroid", "Convex Hull", "Simplify", "Dissolve", "Reproject"]:
            op_copy = op
            self._act(m, op, lambda _, o=op_copy: self._open_geoprocess(initial_op=o))

        # Export
        m = mb.addMenu("&Export")
        for name, exp in EXPORTERS.items():
            self._act(m, f"⬇  Export {name}…",
                      lambda _, n=name: self._export(n))

        # View
        m = mb.addMenu("&Tampilan")
        self._act(m, "🗺  Perbesar Peta",  lambda: self._v_split.setSizes([700, 200]))
        self._act(m, "📋  Perbesar Tabel", lambda: self._v_split.setSizes([200, 500]))
        m.addSeparator()
        self._act(m, "🎨  Refresh Peta", self._map_canvas.toolbar.refresh_clicked.emit, "Ctrl+R")

        # Help
        m = mb.addMenu("&Bantuan")
        self._act(m, "📖  Panduan Lengkap…",          lambda: open_help(self),                        "F1")
        self._act(m, "📂  Panduan Import…",           lambda: open_help(self, "📂  Import File"),      "")
        self._act(m, "📋  Panduan Tabel Atribut…",    lambda: open_help(self, "📋  Tabel Atribut"),    "")
        self._act(m, "🔍  Panduan Query Builder…",    lambda: open_help(self, "🔍  Query Builder"),    "")
        self._act(m, "⚙  Panduan Geoprocessing…",    lambda: open_help(self, "⚙  Geoprocessing"),    "")
        self._act(m, "🔀  Panduan Pipeline Builder…", lambda: open_help(self, "🔀  Pipeline Builder"),"")
        self._act(m, "⌨  Panduan SQL Console…",      lambda: open_help(self, "⌨  SQL Console"),      "")
        m.addSeparator()
        self._act(m, "ℹ  Tentang Spaque",           self._about)

    def _act(self, menu, text: str, slot, shortcut: str = ""):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _wire_toolbar(self):
        tb = self._toolbar
        tb.connect_clicked.connect(self._open_connection)
        tb.refresh_clicked.connect(self._refresh_layers)
        tb.import_clicked.connect(self._open_import)
        tb.query_builder_clicked.connect(self._open_query_builder)
        tb.geoprocess_clicked.connect(self._open_geoprocess)
        tb.pipeline_clicked.connect(self._open_pipeline)
        tb.sql_console_clicked.connect(self._open_sql_console)
        tb.export_clicked.connect(lambda: self._export("GeoJSON"))
        tb.buffer_clicked.connect(lambda: self._open_geoprocess(initial_op="Buffer"))
        tb.intersect_clicked.connect(lambda: self._open_geoprocess(initial_op="Intersect"))
        tb.clip_clicked.connect(lambda: self._open_geoprocess(initial_op="Clip"))
        tb.union_clicked.connect(lambda: self._open_geoprocess(initial_op="Union"))
        tb.centroid_clicked.connect(lambda: self._open_geoprocess(initial_op="Centroid"))

    def _wire_layer_browser(self):
        lb = self._layer_browser
        lb.layer_activated.connect(self._load_layer)
        lb.layer_selected.connect(lambda layer: setattr(self, '_current_layer', layer))
        lb.layer_attributes.connect(self._load_layer_attrs)
        lb.layer_delete_requested.connect(self._delete_layer)
        lb.refresh_requested.connect(self._refresh_layers)

    def _wire_bottom_panel(self):
        bp = self._bottom_panel
        bp.sql_submitted.connect(lambda sql: self._run_sql(sql))
        bp.export_requested.connect(lambda: self._export("GeoJSON"))
        bp.save_edits_requested.connect(self._save_attribute_edits)
        bp.attr_table.open_in_window.connect(self._open_attribute_window)
        bp.attr_table.add_column_requested.connect(self._add_column)
        bp.attr_table.delete_column_requested.connect(self._delete_column)
        bp.attr_table.delete_rows_requested.connect(self._delete_rows)
        bp.attr_table.add_row_requested.connect(self._add_row_from_bottom_panel)
        self._attr_dialogs: List[AttributeTableDialog] = []

    def _connect_log_handler(self):
        handler = get_qt_handler()
        handler.log_emitted.connect(self._bottom_panel.log)

    # ─────────────────────────────────────────────────────────────────────────
    # Connection
    # ─────────────────────────────────────────────────────────────────────────

    def _open_connection(self):
        initial = self._db_conn.params
        dlg = ConnectionDialog(initial, self)
        dlg.params_accepted.connect(self._do_connect)
        dlg.exec()

    def _do_connect(self, params: ConnectionParams):
        self._set_busy(True)
        self.statusBar().showMessage("⏳ Menghubungkan…")
        self._worker_conn = ConnectWorker(self._db_conn, params)
        self._worker_conn.finished.connect(self._on_connected)
        self._worker_conn.start()

    def _on_connected(self, ok: bool, msg: str):
        self._set_busy(False)
        if ok:
            self._postgis  = PostGISDatabase(self._db_conn)
            self._repo     = LayerRepository(self._postgis)
            self._layer_svc = LayerService(self._repo)
            self._query_svc = QueryService(self._repo)
            self._geo_svc  = GeoprocessService(self._repo)
            self._import_svc = ImportService(self._db_conn)

            p = self._db_conn.params
            label = p.safe_label if p else ""
            self._layer_browser.set_connected(True, label)
            self._db_status_lbl.setText(f"  ⬤  {label}  ")
            self._db_status_lbl.setStyleSheet("color:#1e9e6a;font-size:11px;")
            self.statusBar().showMessage(f"✅ Terhubung — {msg}")
            logger.info("Connected: %s | %s", label, msg)

            # Save DB state to project
            if p:
                self._project.update_db_state(p.host, p.port, p.dbname, p.user)
            self._update_title()
            self._refresh_layers()
        else:
            self.statusBar().showMessage("❌ Gagal terhubung")
            QMessageBox.critical(self, "Koneksi Gagal", msg)

    def _disconnect(self):
        self._db_conn.disconnect()
        self._postgis = self._repo = self._layer_svc = None
        self._query_svc = self._geo_svc = None
        self._layer_browser.set_connected(False)
        self._layer_browser.populate([])
        self._db_status_lbl.setText("  ⬤  Tidak terhubung  ")
        self._db_status_lbl.setStyleSheet("color:#e03c4a;font-size:11px;")
        self.statusBar().showMessage("Koneksi diputus")
        logger.info("Disconnected")

    # ─────────────────────────────────────────────────────────────────────────
    # Layer management
    # ─────────────────────────────────────────────────────────────────────────

    def _refresh_layers(self):
        if not self._check_connected():
            return
        try:
            layers = self._layer_svc.refresh_layers()
            self._layer_browser.populate(layers)
            self.statusBar().showMessage(
                f"✅ {len(layers)} layer spasial ditemukan")
        except Exception as exc:
            logger.error("Refresh layers error: %s", exc)

    def _load_layer(self, layer: LayerInfo):
        self._current_layer = layer
        sql = f"SELECT * FROM {layer.qualified_name} LIMIT 5000"
        self._project.update_active_layer(
            layer.schema, layer.table_name, layer.geom_col, sql, layer.display_name
        )
        self._run_query(sql, layer.geom_col, title=layer.display_name)

    def _delete_selected_layer(self):
        layer = self._layer_browser.selected_layer()
        if layer:
            self._delete_layer(layer)
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Info", "Pilih layer dari panel kiri")

    def _load_selected_layer(self):
        layer = self._layer_browser.selected_layer()
        if layer:
            self._load_layer(layer)
        else:
            QMessageBox.information(self, "Info", "Pilih layer dari panel kiri")

    def _load_layer_attrs(self, layer: LayerInfo):
        self._current_layer = layer
        sql = f"SELECT * FROM {layer.qualified_name} LIMIT 5000"
        self._run_query(sql, layer.geom_col, title=layer.display_name)
        self._bottom_panel._tabs.setCurrentIndex(0)

    def _view_selected_attrs(self):
        layer = self._layer_browser.selected_layer()
        if layer:
            self._load_layer_attrs(layer)

    def _delete_layer(self, layer):
        """Hapus tabel dari PostGIS setelah konfirmasi."""
        from PyQt6.QtWidgets import QMessageBox
        ans = QMessageBox.question(
            self,
            "Konfirmasi Hapus Tabel",
            f"Yakin ingin menghapus tabel\n\n"
            f'  \"{layer.schema}\".\"{layer.table_name}\"\n\n'
            "dari database PostGIS?\n\n"
            "⚠️  Tindakan ini PERMANEN dan tidak bisa dibatalkan!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            cur = self._db_conn.cursor()
            cur.execute(
                f'DROP TABLE IF EXISTS "{layer.schema}"."{layer.table_name}" CASCADE'
            )
            self._db_conn.commit()
            cur.close()
            logger.info("Tabel dihapus: %s.%s", layer.schema, layer.table_name)
            self.statusBar().showMessage(
                f"🗑 Tabel '{layer.table_name}' berhasil dihapus")
            # Clear peta jika layer yang dihapus sedang aktif
            if (self._current_layer and
                self._current_layer.table_name == layer.table_name):
                self._current_layer = None
                self._current_gdf   = None
                self._map_canvas.clear()
                self._bottom_panel.attr_table.clear()
            self._refresh_layers()
        except Exception as exc:
            logger.error("Delete layer error: %s", exc)
            QMessageBox.critical(self, "Gagal Menghapus", str(exc))

    def _show_layer_stats(self):
        layer = self._layer_browser.selected_layer()
        if not layer:
            QMessageBox.information(self, "Info", "Pilih layer terlebih dahulu")
            return
        try:
            count = self._layer_svc.get_row_count(layer)
            cols  = self._layer_svc.get_columns(layer)
            info  = (
                f"Layer: {layer.full_label}\n"
                f"Geometri: {layer.geom_type}\n"
                f"SRID: {layer.srid}\n"
                f"Kolom geometri: {layer.geom_col}\n"
                f"Jumlah fitur: {count:,}\n"
                f"Jumlah kolom: {len(cols)}\n\n"
                f"Kolom:\n" +
                "\n".join(f"  • {c.name}  ({c.data_type})" for c in cols)
            )
            QMessageBox.information(self, f"Statistik — {layer.display_name}", info)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    # ─────────────────────────────────────────────────────────────────────────
    # Query execution
    # ─────────────────────────────────────────────────────────────────────────

    def _run_query(self, sql: str, geom_col: Optional[str] = None, title: str = ""):
        if not self._check_connected():
            return
        self._set_busy(True)
        self.statusBar().showMessage("⏳ Menjalankan query…")
        logger.info("Query: %.120s", sql)

        self._query_worker = QueryWorker(self._query_svc, sql, geom_col)
        self._query_worker.finished.connect(
            lambda result: self._on_query_done(result, title))
        self._query_worker.start()

    def _on_query_done(self, result: QueryResult, title: str):
        self._set_busy(False)
        if result.has_error:
            self.statusBar().showMessage(f"❌ {result.error[:80]}")
            logger.error("Query error: %s", result.error)
            QMessageBox.critical(self, "Query Error", result.error)
            self._bottom_panel.sql_console.set_status(result.error, error=True)
            return

        self._current_gdf = result.gdf
        self.statusBar().showMessage(
            f"✅ {result.row_count:,} baris — {title}")
        logger.info("Query OK: %d rows", result.row_count)

        # Track in project history
        self._project.add_to_history(result.sql, title, result.row_count)
        self._update_title()

        # Detect PK column for edit support (coba dari DB dulu)
        pk_col = None
        if self._current_layer:
            pk_col = self._detect_pk_from_db(self._current_layer)
        if not pk_col:
            pk_col = self._detect_pk_col(result.columns)
        geom_type = self._current_layer.geom_type if self._current_layer else ""
        geom_col = result.gdf.geometry.name if result.gdf is not None else ""
        # Populate attribute table
        self._bottom_panel.attr_table.set_layer_name(title)
        self._bottom_panel.populate_table(result.columns, result.rows, pk_col=pk_col, geom_type=geom_type, geom_col=geom_col)

        # Update map choropleth column list
        numeric_cols: List[str] = []
        if result.gdf is not None:
            numeric_cols = [
                c for c in result.gdf.columns
                if result.gdf[c].dtype.kind in ('i', 'f')
                   and c != result.gdf.geometry.name
            ]

        # Render map
        if result.has_geometry:
            self._map_canvas.display(result.gdf, title, numeric_cols)
        else:
            self._bottom_panel._tabs.setCurrentIndex(0)

    def _run_sql(self, sql: str):
        """Called from SQL console."""
        geom_col = self._current_layer.geom_col if self._current_layer else None
        self._run_query(sql, geom_col, title="SQL Console")

    def _open_attribute_window(self, layer_name: str):
        """Buka attribute table dalam window terpisah dengan semua baris."""
        if not self._current_layer:
            QMessageBox.warning(self, "Peringatan", "Tidak ada layer aktif.")
            return
        layer = self._current_layer
        result = self._query_svc.fetch_all_rows(layer.qualified_name, layer.geom_col)
        if result.has_error:
            QMessageBox.critical(self, "Error", result.error)
            return
        pk_col = self._detect_pk_from_db(layer) or self._detect_pk_col(result.columns)
        geom_col = result.gdf.geometry.name if result.gdf is not None else layer.geom_col

        dlg = AttributeTableDialog(layer_name, self)
        dlg.save_edits_requested.connect(self._save_attribute_edits_from_dialog)
        dlg.add_row_requested.connect(self._add_row_from_dialog)
        dlg.add_column_requested.connect(self._add_column)
        dlg.delete_column_requested.connect(self._delete_column)
        dlg.delete_rows_requested.connect(self._delete_rows)
        dlg.closed.connect(self._on_attr_window_closed)
        self._attr_dialogs.append(dlg)
        dlg.populate_table(
            result.columns,
            result.rows,
            pk_col,
            layer.geom_type,
            geom_col,
        )
        dlg.show()

    def _on_attr_window_closed(self, layer_name: str):
        """Cleanup when attribute window is closed."""
        for dlg in self._attr_dialogs:
            if dlg._layer_name == layer_name:
                self._attr_dialogs.remove(dlg)
                break

    def _detect_pk_col(self, columns) -> Optional[str]:
        """Deteksi kolom primary key dari daftar kolom hasil query."""
        # Urutan prioritas: kolom umum PK + _gid yang dibuat Spaque saat geoprocess
        pk_candidates = (
            "gid", "id", "fid", "ogc_fid", "objectid", "feat_id", "pk",
            "_gid", "oid", "feature_id", "rowid",
        )
        col_lower = {c.lower(): c for c in columns}
        for cand in pk_candidates:
            if cand in col_lower:
                return col_lower[cand]
        # Fallback: coba query DB untuk cek constraint PRIMARY KEY
        # (dilakukan di _detect_pk_from_db jika layer tersedia)
        return None

    def _detect_pk_from_db(self, layer) -> Optional[str]:
        """Query information_schema untuk mendapatkan PK aktual dari DB."""
        if not self._check_connected():
            return None
        try:
            cur = self._db_conn.cursor()
            cur.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s
                  AND tc.table_name  = %s
                LIMIT 1
            """, (layer.schema, layer.table_name))
            row = cur.fetchone()
            cur.close()
            return row[0] if row else None
        except Exception:
            return None

    def _save_attribute_edits(self, edits: dict):
        """
        Simpan perubahan atribut ke PostGIS via UPDATE.
        edits = {(row_idx, col_name): new_value_str}
        """
        if not self._current_layer:
            QMessageBox.warning(self, "Peringatan",
                                "Tidak ada layer aktif untuk disimpan.")
            return
        if not self._check_connected():
            return

        layer  = self._current_layer
        attr_table = self._bottom_panel.attr_table
        pk_col = attr_table._pk_col

        rows_edits: Dict[int, Dict[str, str]] = {}
        for (row_idx, col_name), new_val in edits.items():
            rows_edits.setdefault(row_idx, {})[col_name] = new_val

        errors   = []
        success_count = 0
        cur = None
        try:
            cur = self._db_conn.cursor()
            for row_idx, col_vals in rows_edits.items():
                if pk_col:
                    pk_val = attr_table.get_pk_value(row_idx)
                    if pk_val is None:
                        errors.append(f"Baris {row_idx}: nilai PK tidak ditemukan, dilewati")
                        continue
                    safe_cols = {
                        col: val for col, val in col_vals.items()
                        if col != pk_col and col != layer.geom_col
                    }
                    if not safe_cols:
                        continue
                    set_clause = ", ".join(f'"{col}" = %s' for col in safe_cols)
                    vals = list(safe_cols.values()) + [pk_val]
                    sql = (
                        f'UPDATE {layer.qualified_name} '
                        f'SET {set_clause} '
                        f'WHERE "{pk_col}" = %s'
                    )
                    cur.execute(sql, vals)
                    success_count += 1
                else:
                    safe_cols = {
                        col: val for col, val in col_vals.items()
                        if col != layer.geom_col
                    }
                    if not safe_cols:
                        continue
                    orig_row = attr_table._rows[row_idx] if row_idx < len(attr_table._rows) else []
                    orig_cols = attr_table._columns
                    where_parts = []
                    where_vals = []
                    for ci, col in enumerate(orig_cols):
                        if col != layer.geom_col and col in safe_cols:
                            where_parts.append(f'"{col}" = %s')
                            where_vals.append(orig_row[ci] if ci < len(orig_row) else None)
                    if not where_parts:
                        errors.append(f"Baris {row_idx}: tidak bisa identifikasi baris")
                        continue
                    set_clause = ", ".join(f'"{col}" = %s' for col in safe_cols)
                    where_clause = " AND ".join(where_parts)
                    vals = list(safe_cols.values()) + where_vals
                    sql = (
                        f'UPDATE {layer.qualified_name} '
                        f'SET {set_clause} '
                        f'WHERE {where_clause}'
                    )
                    cur.execute(sql, vals)
                    if cur.rowcount > 0:
                        success_count += 1
                    else:
                        errors.append(f"Baris {row_idx}: baris tidak ditemukan atau sudah berubah")

            self._db_conn.commit()

        except Exception as exc:
            try:
                self._db_conn.rollback()
            except Exception:
                pass
            logger.error("Save edits failed: %s", exc)
            QMessageBox.critical(
                self, "Gagal Menyimpan Perubahan",
                f"Error saat UPDATE ke database:\n\n{exc}"
            )
            return
        finally:
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass

        # Tampilkan hasil
        msg_parts = [f"✅ {success_count} baris diperbarui di {layer.full_label}"]
        if errors:
            msg_parts.append(f"⚠ {len(errors)} baris dilewati: " + "; ".join(errors[:3]))
        self.statusBar().showMessage("  ".join(msg_parts))
        logger.info("Edits saved: %d rows updated in %s", success_count, layer.full_label)

        # Reset tabel edit state
        self._bottom_panel.attr_table.mark_save_done()

        # Reload data segar dari DB
        self._load_layer(layer)

    def _save_attribute_edits_from_dialog(self, dialog, edits: dict):
        """
        Simpan perubahan dari popup window.
        Berbeda dari _save_attribute_edits (bottom panel):
        sumber data diambil dari dialog, bukan self._bottom_panel.attr_table.
        """
        if not self._current_layer:
            QMessageBox.warning(self, "Peringatan", "Tidak ada layer aktif.")
            return
        if not self._check_connected():
            return

        layer  = self._current_layer
        pk_col = dialog._pk_col

        if not pk_col:
            QMessageBox.warning(
                self, "Tidak Bisa Simpan",
                "Tabel tidak memiliki Primary Key.\n"
                "Perubahan tidak bisa disimpan ke database.")
            return

        rows_edits: Dict[int, Dict[str, str]] = {}
        for (global_row, col_name), new_val in edits.items():
            rows_edits.setdefault(global_row, {})[col_name] = new_val

        errors, success_count = [], 0
        cur = None
        try:
            cur = self._db_conn.cursor()
            for global_row, col_vals in rows_edits.items():
                pk_val = dialog.get_pk_value_global(global_row)
                if pk_val is None:
                    errors.append(f"Baris {global_row}: PK tidak ditemukan")
                    continue
                safe_cols = {
                    col: val for col, val in col_vals.items()
                    if col != pk_col and col != layer.geom_col
                }
                if not safe_cols:
                    continue
                set_clause = ", ".join(f'"{col}" = %s' for col in safe_cols)
                vals = list(safe_cols.values()) + [pk_val]
                sql  = (f'UPDATE {layer.qualified_name} '
                        f'SET {set_clause} WHERE "{pk_col}" = %s')
                cur.execute(sql, vals)
                success_count += 1
            self._db_conn.commit()
        except Exception as exc:
            try: self._db_conn.rollback()
            except Exception: pass
            logger.error("Save dialog edits failed: %s", exc)
            QMessageBox.critical(self, "Gagal Menyimpan", f"Error:\n\n{exc}")
            return
        finally:
            if cur:
                try: cur.close()
                except Exception: pass

        msg_parts = [f"✅ {success_count} baris diperbarui di {layer.full_label}"]
        if errors:
            msg_parts.append(f"⚠ {len(errors)} dilewati: " + "; ".join(errors[:3]))
        self.statusBar().showMessage("  ".join(msg_parts))
        logger.info("Dialog edits saved: %d rows in %s", success_count, layer.full_label)
        dialog.mark_save_done()
        self._load_layer(layer)

    def _add_row_from_dialog(self, dialog, row_data: dict):
        """Tambah baris baru ke tabel non-spasial dari popup window."""
        if not self._current_layer or not self._check_connected():
            return
        layer = self._current_layer
        if not row_data:
            return
        try:
            cols = [f'"{c}"' for c in row_data]
            placeholders = ", ".join(["%s"] * len(row_data))
            vals = list(row_data.values())
            sql  = (f'INSERT INTO {layer.qualified_name} '
                    f'({", ".join(cols)}) VALUES ({placeholders})')
            cur = self._db_conn.cursor()
            cur.execute(sql, vals)
            self._db_conn.commit()
            cur.close()
            self.statusBar().showMessage(f"✅ Baris baru ditambahkan ke {layer.full_label}")
            logger.info("Row added to %s", layer.full_label)
            # Reload popup window dengan data terbaru
            self._refresh_all_attr_windows(layer)
            self._load_layer(layer)
        except Exception as exc:
            try: self._db_conn.rollback()
            except Exception: pass
            logger.error("Add row failed: %s", exc)
            QMessageBox.critical(self, "Gagal Tambah Baris", f"Error:\n\n{exc}")

    def _add_row_from_bottom_panel(self, row_data: dict):
        """Tambah baris baru dari bottom panel (non-spasial)."""
        if not self._current_layer or not self._check_connected():
            return
        layer = self._current_layer
        if not row_data:
            return
        try:
            cols = [", ".join(f'"{c}"' for c in row_data)]
            placeholders = ", ".join(["%s"] * len(row_data))
            col_clause   = ", ".join(f'"{c}"' for c in row_data)
            vals = list(row_data.values())
            sql  = (f'INSERT INTO {layer.qualified_name} '
                    f'({col_clause}) VALUES ({placeholders})')
            cur = self._db_conn.cursor()
            cur.execute(sql, vals)
            self._db_conn.commit()
            cur.close()
            self.statusBar().showMessage(f"✅ Baris baru ditambahkan ke {layer.full_label}")
            logger.info("Row added (bottom panel) to %s", layer.full_label)
            self._refresh_all_attr_windows(layer)
            self._load_layer(layer)
        except Exception as exc:
            try: self._db_conn.rollback()
            except Exception: pass
            logger.error("Add row (bottom) failed: %s", exc)
            QMessageBox.critical(self, "Gagal Tambah Baris", f"Error:\n\n{exc}")

    def _add_column(self, col_name: str, data_type: str = "TEXT"):
        """Tambah kolom baru ke tabel di database."""
        if not self._check_connected():
            return
        layer = self._current_layer
        if not layer:
            QMessageBox.warning(self, "Peringatan", "Tidak ada layer aktif.")
            return
        sql = f'ALTER TABLE {layer.qualified_name} ADD COLUMN "{col_name}" {data_type}'
        try:
            cur = self._db_conn.cursor()
            cur.execute(sql)
            self._db_conn.commit()
            cur.close()
            self.statusBar().showMessage(f"✅ Kolom '{col_name}' ({data_type}) ditambahkan")
            if self._repo:
                self._repo.invalidate_cache()
            self._load_layer(layer)
            self._refresh_all_attr_windows(layer)
        except Exception as exc:
            self._db_conn.rollback()
            logger.error("Add column failed: %s", exc)
            QMessageBox.critical(self, "Gagal Menambah Kolom",
                               f"Error:\n\n{exc}")

    def _delete_column(self, col_name: str):
        """Hapus kolom dari tabel di database."""
        if not self._check_connected():
            return
        layer = self._current_layer
        if not layer:
            QMessageBox.warning(self, "Peringatan", "Tidak ada layer aktif.")
            return
        sql = f'ALTER TABLE {layer.qualified_name} DROP COLUMN "{col_name}"'
        try:
            cur = self._db_conn.cursor()
            cur.execute(sql)
            self._db_conn.commit()
            cur.close()
            self.statusBar().showMessage(f"✅ Kolom '{col_name}' dihapus")
            if self._repo:
                self._repo.invalidate_cache()
            self._load_layer(layer)
            self._refresh_all_attr_windows(layer)
        except Exception as exc:
            self._db_conn.rollback()
            logger.error("Delete column failed: %s", exc)
            QMessageBox.critical(self, "Gagal Menghapus Kolom",
                               f"Error:\n\n{exc}")

    def _refresh_all_attr_windows(self, layer):
        """Setelah DDL (add/delete column), reload semua popup attribute window."""
        if not self._attr_dialogs:
            return
        try:
            result = self._query_svc.fetch_all_rows(layer.qualified_name, layer.geom_col)
            if result.has_error:
                return
            pk_col   = self._detect_pk_from_db(layer) or self._detect_pk_col(result.columns)
            geom_col = result.gdf.geometry.name if result.gdf is not None else layer.geom_col
            for dlg in self._attr_dialogs:
                if dlg._layer_name in (layer.table_name, layer.full_label):
                    dlg.refresh_populate(
                        result.columns, result.rows,
                        pk_col, layer.geom_type, geom_col,
                    )
        except Exception as exc:
            logger.warning("refresh_all_attr_windows: %s", exc)

    def _delete_rows(self, pk_values: list):
        """Hapus baris dari tabel berdasarkan PK atau row data."""
        if not self._check_connected():
            return
        layer = self._current_layer
        if not layer:
            QMessageBox.warning(self, "Peringatan", "Tidak ada layer aktif.")
            return
        attr_table = self._bottom_panel.attr_table
        pk_col = attr_table._pk_col
        try:
            cur = self._db_conn.cursor()
            deleted = 0
            for row_idx in pk_values:
                if pk_col:
                    pk_val = attr_table.get_pk_value(row_idx)
                    if pk_val is None:
                        continue
                    sql = f'DELETE FROM {layer.qualified_name} WHERE "{pk_col}" = %s'
                    cur.execute(sql, (pk_val,))
                else:
                    orig_row = attr_table._rows[row_idx] if row_idx < len(attr_table._rows) else []
                    orig_cols = attr_table._columns
                    where_parts = []
                    where_vals = []
                    for ci, col in enumerate(orig_cols):
                        if col != layer.geom_col:
                            where_parts.append(f'"{col}" = %s')
                            where_vals.append(orig_row[ci] if ci < len(orig_row) else None)
                    if where_parts:
                        where_clause = " AND ".join(where_parts)
                        sql = f'DELETE FROM {layer.qualified_name} WHERE {where_clause}'
                        cur.execute(sql, where_vals)
                deleted += cur.rowcount
            self._db_conn.commit()
            cur.close()
            self.statusBar().showMessage(f"✅ {deleted} baris dihapus")
            self._load_layer(layer)
        except Exception as exc:
            self._db_conn.rollback()
            logger.error("Delete rows failed: %s", exc)
            QMessageBox.critical(self, "Gagal Menghapus Baris",
                               f"Error:\n\n{exc}")

    # ─────────────────────────────────────────────────────────────────────────
    # Dialogs
    # ─────────────────────────────────────────────────────────────────────────

    def _open_import(self):
        """Open spatial file import dialog."""
        if not self._check_connected():
            return
        dlg = ImportDialog(self._import_svc, self)
        dlg.import_done.connect(self._on_import_done)
        dlg.exec()

    def _on_import_done(self, result):
        """Called after successful import — refresh layers and show result on map."""
        logger.info("Import done: %s.%s (%d rows)", result.schema, result.table, result.rows_imported)
        self.statusBar().showMessage(
            f"✅ Import selesai: {result.rows_imported:,} fitur → "
            f'"{result.schema}"."{result.table}"'
        )
        # Refresh layer tree
        self._refresh_layers()
        # Auto-load the imported layer on the map
        if result.table:
            sql = f'SELECT * FROM "{result.schema}"."{result.table}" LIMIT 5000'
            self._run_query(sql, title=result.table)

    def _open_query_builder(self):
        if not self._check_connected():
            return
        layers = self._layer_svc.get_layers()
        if not layers:
            QMessageBox.warning(self, "Peringatan", "Tidak ada layer spasial.")
            return
        dlg = QueryBuilderDialog(
            layers, self._layer_svc.get_columns,
            db=self._db_conn, parent=self)
        dlg.sql_ready.connect(self._run_query)
        dlg.sql_save.connect(self._save_query_result)
        dlg.exec()

    def _save_query_result(self, sql: str, geom_col: str, table_name: str):
        """Simpan hasil query sebagai tabel PostGIS — seamless workflow."""
        if not self._check_connected():
            return
        self._set_busy(True)
        self.statusBar().showMessage(f"⏳ Menyimpan hasil query ke tabel '{table_name}'…")
        ok, msg, count = self._postgis.create_table_from_sql(sql, "public", table_name)
        self._set_busy(False)
        if ok:
            self.statusBar().showMessage(f"✅ {msg}")
            logger.info(msg)
            self._refresh_layers()
            # Load hasil ke peta
            load_sql = f'SELECT * FROM "public"."{table_name}" LIMIT 5000'
            self._run_query(load_sql, geom_col, title=table_name)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Tersimpan",
                f"{msg}\n\nTabel '{table_name}' kini tersedia di Layer Panel\n"
                "dan bisa langsung dipakai sebagai input Geoprocessing."
            )
        else:
            self.statusBar().showMessage(f"❌ Gagal menyimpan: {msg[:60]}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Gagal Simpan", msg)

    def _open_geoprocess(self, _checked=False, initial_op: str = ""):
        if not self._check_connected():
            return
        layers = self._layer_svc.get_layers()
        if not layers:
            QMessageBox.warning(self, "Peringatan", "Tidak ada layer spasial.")
            return
        dlg = GeoprocessDialog(
            layers, self._layer_svc.get_columns, initial_op, self)
        dlg.spec_accepted.connect(self._run_geoprocess)
        dlg.exec()

    def _open_sql_console(self):
        self._bottom_panel.show_sql_console()

    def _open_pipeline(self):
        """Open Visual Pipeline Builder dialog."""
        if not self._check_connected():
            return
        layers = self._layer_svc.get_layers()
        if not layers:
            QMessageBox.warning(self, "Peringatan",
                                "Tidak ada layer spasial di database.")
            return
        dlg = PipelineDialog(
            layers=layers,
            get_columns=self._layer_svc.get_columns,
            repo=self._repo,
            parent=self,
        )
        dlg.pipeline_executed.connect(self._on_pipeline_done)
        dlg.exec()

    def _on_pipeline_done(self, result):
        """Called after pipeline execution completes."""
        self._refresh_layers()

        # Cari tabel aktual dari step Output node (bisa berbeda dari result.output_table
        # jika rename gagal dan nama geoprocess dipakai)
        actual_table  = result.output_table
        actual_schema = result.output_schema

        # Cek apakah ada step Output yang punya sql_subquery (berisi nama tabel aktual)
        for step in reversed(result.steps):
            if step.sql_subquery and step.sql_subquery.startswith('SELECT * FROM "'):
                # Parse: SELECT * FROM "schema"."table"
                import re
                m = re.search(r'FROM "([^"]+)"\."([^"]+)"', step.sql_subquery)
                if m:
                    actual_schema = m.group(1)
                    actual_table  = m.group(2)
                    break

        self.statusBar().showMessage(
            f"✅ Pipeline selesai → {actual_schema}.{actual_table}"
        )
        if actual_table:
            sql = f'SELECT * FROM "{actual_schema}"."{actual_table}" LIMIT 5000'
            self._run_query(sql, title=actual_table)

    # ─────────────────────────────────────────────────────────────────────────
    # Geoprocessing
    # ─────────────────────────────────────────────────────────────────────────

    def _run_geoprocess(self, spec: GeoprocessSpec):
        if not self._check_connected():
            return
        self._set_busy(True)
        self.statusBar().showMessage(f"⏳ Geoprocessing: {spec.operation}…")
        logger.info("Geoprocess: %s → %s.%s",
                    spec.operation, spec.output_schema, spec.output_table)

        self._geo_worker = GeoWorker(self._geo_svc, spec)
        self._geo_worker.finished.connect(self._on_geoprocess_done)
        self._geo_worker.start()

    def _on_geoprocess_done(self, result):
        self._set_busy(False)
        if result.has_error:
            self.statusBar().showMessage("❌ Geoprocess gagal")
            logger.error("Geoprocess error: %s", result.message)
            QMessageBox.critical(self, "Geoprocessing Gagal", result.message)
            return

        self.statusBar().showMessage(f"✅ {result.message}")
        logger.info(result.message)

        # Refresh layer list (new table was created)
        self._refresh_layers()

        # Display result on map
        if result.gdf is not None:
            self._current_gdf = result.gdf
            numeric_cols = [
                c for c in result.gdf.columns
                if result.gdf[c].dtype.kind in ('i', 'f')
                   and c != result.gdf.geometry.name
            ]
            self._map_canvas.display(
                result.gdf, result.output_table, numeric_cols)
            cols = list(result.gdf.columns)
            rows = result.gdf.head(5000).values.tolist()
            self._bottom_panel.populate_table(cols, rows)

        QMessageBox.information(self, "Berhasil", result.message)

    # ─────────────────────────────────────────────────────────────────────────
    # Export
    # ─────────────────────────────────────────────────────────────────────────

    def _export(self, format_name: str = "GeoJSON"):
        if self._current_gdf is None:
            # Cek apakah layer aktif adalah non-spasial (tidak punya geometri)
            if self._current_layer and not self._current_layer.geom_col:
                QMessageBox.information(
                    self, "Tabel Non-Spasial",
                    "Tabel ini tidak memiliki kolom geometri (non-spasial).\n\n"
                    "Data atribut bisa diexport sebagai CSV melalui:\n"
                    "  • Menu Export → Export CSV\n"
                    "  • Atau jalankan query di SQL Console, lalu export hasilnya.\n\n"
                    "Untuk export GeoJSON/Shapefile diperlukan data spasial.")
                # Jika format CSV, coba export dari baris di tabel atribut
                if format_name == "CSV":
                    self._export_non_spatial_csv()
                return
            QMessageBox.information(self, "Info", "Belum ada data untuk diexport.\n"
                                                   "Muat layer terlebih dahulu.")
            return
        exp = EXPORTERS.get(format_name)
        if not exp:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, f"Export {format_name}", f"hasil{exp.extension}", exp.file_filter)
        if not path:
            return
        ok, msg = exp.export(self._current_gdf, Path(path))
        if ok:
            QMessageBox.information(self, "Export Berhasil", msg)
        else:
            QMessageBox.critical(self, "Export Gagal", msg)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _export_non_spatial_csv(self):
        """Export tabel non-spasial sebagai CSV dari data yang ada di tabel atribut."""
        attr = self._bottom_panel.attr_table
        if not attr._columns or not attr._rows:
            QMessageBox.information(self, "Info", "Tidak ada data di tabel atribut.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "hasil.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            import csv as _csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = _csv.writer(f)
                writer.writerow(attr._columns)
                writer.writerows(attr._rows)
            QMessageBox.information(
                self, "Export Berhasil",
                f"✅ {len(attr._rows):,} baris diexport ke {Path(path).name}")
            logger.info("Non-spatial CSV exported: %s (%d rows)", path, len(attr._rows))
        except Exception as exc:
            QMessageBox.critical(self, "Export Gagal", str(exc))

    def _check_connected(self) -> bool:
        if not self._db_conn.is_connected:
            QMessageBox.warning(
                self, "Belum Terhubung",
                "Hubungkan ke database PostGIS terlebih dahulu.\n"
                "Gunakan tombol 🔌 Koneksi di toolbar."
            )
            return False
        return True

    def _set_busy(self, busy: bool):
        self._progress.setVisible(busy)
        QApplication.processEvents()

    # ─────────────────────────────────────────────────────────────────────────
    # Project management
    # ─────────────────────────────────────────────────────────────────────────

    def _update_title(self):
        """Sync window title with project state."""
        self.setWindowTitle(
            f"{self._project.window_title} — {AppConfig.APP_NAME} v{AppConfig.APP_VERSION}"
        )

    def _project_new(self):
        if self._project.is_dirty:
            ans = ask_save_changes(self, self._project.project_name)
            if ans == "save":
                self._project_save()
            elif ans == "cancel":
                return

        self._project.new_project()
        self._update_title()
        self.statusBar().showMessage("📄 Project baru dibuat")
        logger.info("New project created")

    def _project_open(self):
        if self._project.is_dirty:
            ans = ask_save_changes(self, self._project.project_name)
            if ans == "save":
                self._project_save()
            elif ans == "cancel":
                return

        path, _ = QFileDialog.getOpenFileName(
            self, "Buka Project Spaque", "",
            f"Spaque Project (*{SPQ_EXTENSION});;Semua File (*.*)"
        )
        if path:
            self._load_project(Path(path))

    def _project_open_recent(self):
        recent = self._project.get_recent_files()
        dlg = RecentProjectsDialog(recent, self)
        dlg.file_selected.connect(self._load_project)
        dlg.exec()

    def _load_project(self, path: Path):
        """Load .spq and restore session state."""
        state, msg = self._project.open(path)
        if not state:
            QMessageBox.critical(self, "Gagal Membuka Project", msg)
            return

        self.statusBar().showMessage(f"📂 {msg}")
        self._update_title()
        self._rebuild_recent_menu()

        # Restore window geometry
        w  = state.window
        if w.x >= 0 and w.y >= 0:
            self.setGeometry(w.x, w.y, w.width, w.height)
        else:
            self.resize(w.width, w.height)
        if w.maximized:
            self.showMaximized()
        if w.h_split_sizes:
            self._h_split.setSizes(w.h_split_sizes)
        if w.v_split_sizes:
            self._v_split.setSizes(w.v_split_sizes)

        # Restore SQL console
        if state.sql_console.text:
            self._bottom_panel.sql_console._editor.setPlainText(state.sql_console.text)

        # Restore DB connection if info available
        db = state.db
        if db.dbname:
            hint = (f"Project ini terakhir terhubung ke:\n\n"
                    f"  Host     : {db.host}:{db.port}\n"
                    f"  Database : {db.dbname}\n"
                    f"  User     : {db.user}\n\n"
                    "Hubungkan sekarang?")
            ans = QMessageBox.question(
                self, "Restore Koneksi Database", hint,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans == QMessageBox.StandardButton.Yes:
                self._open_connection()

        logger.info("Project opened: %s", path.name)

    def _project_save(self) -> bool:
        """Save current project. Returns True if successful."""
        if not self._project.current_path:
            return self._project_save_as()

        # Capture SQL console state before saving
        sql_text = self._bottom_panel.sql_console._editor.toPlainText()
        self._project.update_sql_console(sql_text)

        ok, msg = self._project.save()
        self.statusBar().showMessage(f"{'💾' if ok else '❌'}  {msg}")
        self._update_title()
        if not ok:
            QMessageBox.critical(self, "Gagal Menyimpan", msg)
        return ok

    def _project_save_as(self) -> bool:
        """Save As dialog. Returns True if saved."""
        default = (str(self._project.current_path)
                   if self._project.current_path
                   else f"{self._project.project_name}.spq")
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Project Sebagai", default,
            f"Spaque Project (*{SPQ_EXTENSION});;Semua File (*.*)"
        )
        if not path:
            return False

        # Capture SQL console
        sql_text = self._bottom_panel.sql_console._editor.toPlainText()
        self._project.update_sql_console(sql_text)

        ok, msg = self._project.save_as(Path(path))
        self.statusBar().showMessage(f"{'💾' if ok else '❌'}  {msg}")
        self._update_title()
        self._rebuild_recent_menu()
        if not ok:
            QMessageBox.critical(self, "Gagal Menyimpan", msg)
        return ok

    def _project_properties(self):
        dlg = ProjectPropertiesDialog(self._project.state, self)
        if dlg.exec():
            self._project.mark_dirty()
            self._update_title()

    def _rebuild_recent_menu(self):
        """Rebuild the recent-files submenu."""
        self._recent_menu.clear()
        recent = self._project.get_recent_files()
        if not recent:
            act = self._recent_menu.addAction("(Belum ada)")
            act.setEnabled(False)
        else:
            for path in recent:
                act = self._recent_menu.addAction(f"📁  {path.name}")
                act.setStatusTip(str(path))
                act.triggered.connect(lambda _, p=path: self._load_project(p))
            self._recent_menu.addSeparator()
            clr = self._recent_menu.addAction("🗑  Bersihkan Daftar")
            clr.triggered.connect(self._clear_recent_menu)

    def _clear_recent_menu(self):
        from core.project.service import _RECENT_FILE
        try:
            _RECENT_FILE.write_text('{"recent":[]}')
        except Exception:
            pass
        self._rebuild_recent_menu()

    def _about(self):
        QMessageBox.about(
            self, f"Tentang {AppConfig.APP_NAME}",
            f"<h2>🌍 {AppConfig.APP_NAME}</h2>"
            f"<p>Desktop GIS untuk PostGIS — v{AppConfig.APP_VERSION}</p>"
            f"<p><b>Stack:</b> Python · PyQt6 · GeoPandas · Folium · PostGIS</p>"
            f"<hr>"
            f"<p><b>Fitur:</b></p>"
            f"<ul>"
            f"<li>Save / Load Project (.spq) dengan riwayat query & bookmark</li>"
            f"<li>Import file spasial: SHP, GeoJSON, GPKG, KML, CSV, dll.</li>"
            f"<li>Koneksi PostgreSQL/PostGIS</li>"
            f"<li>Visual Query Builder (WHERE tanpa SQL)</li>"
            f"<li>Geoprocessing: Buffer, Intersect, Clip, Union, Dissolve, …</li>"
            f"<li>Peta interaktif Folium + Choropleth mapping</li>"
            f"<li>Export GeoJSON / Shapefile / CSV</li>"
            f"<li>SQL Console bebas</li>"
            f"</ul>"
        )

    def closeEvent(self, event: QCloseEvent):
        # Save window state
        geom = self.geometry()
        self._project.update_window_state(
            width=geom.width(), height=geom.height(),
            x=geom.x(), y=geom.y(),
            maximized=self.isMaximized(),
            h_split=self._h_split.sizes(),
            v_split=self._v_split.sizes(),
        )

        # Close all attribute table dialogs
        for dlg in self._attr_dialogs[:]:
            dlg.close()
            dlg.deleteLater()
        self._attr_dialogs.clear()

        # Prompt save if dirty
        if self._project.is_dirty:
            ans = ask_save_changes(self, self._project.project_name)
            if ans == "save":
                ok, msg = self._project.save()
                if not ok:
                    # Save-as if no path yet
                    saved = self._project_save_as()
                    if not saved:
                        event.ignore()
                        return
            elif ans == "cancel":
                event.ignore()
                return
            # "discard" falls through

        self._db_conn.disconnect()
        logger.info("Application closed")
        event.accept()
