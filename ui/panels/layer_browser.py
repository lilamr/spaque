"""
ui/panels/layer_browser.py — Left panel: layer tree + metadata footer
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QLabel,
    QTreeWidget, QTreeWidgetItem, QLineEdit,
    QPushButton, QHBoxLayout, QMenu,
)

from core.domain.entities.layer import LayerInfo
from utils.constants import GEOM_ICONS


class LayerBrowser(QWidget):
    """
    Left sidebar: shows all PostGIS layers grouped by schema.
    Emits signals when user interacts with layers.
    """

    layer_selected        = pyqtSignal(LayerInfo)   # single click
    layer_activated       = pyqtSignal(LayerInfo)   # double-click → load map
    layer_attributes      = pyqtSignal(LayerInfo)   # right-click → attributes
    layer_delete_requested= pyqtSignal(LayerInfo)   # right-click → delete
    refresh_requested     = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(360)
        self._layers: List[LayerInfo] = []
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        hdr = QFrame()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            "background:#0f1116;border-bottom:1px solid #2d3340;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 8, 0)
        lbl = QLabel("LAYER PANEL")
        lbl.setStyleSheet(
            "color:#6a7590;font-size:10px;font-weight:bold;"
            "letter-spacing:1px;background:transparent;border:none;"
        )
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.setObjectName("secondary")
        refresh_btn.setToolTip("Refresh layer (F5)")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        hl.addWidget(lbl)
        hl.addStretch()
        hl.addWidget(refresh_btn)
        layout.addWidget(hdr)

        # Connection banner
        self.conn_banner = _ConnectionBanner()
        layout.addWidget(self.conn_banner)

        # Search box
        search_frame = QFrame()
        search_frame.setFixedHeight(38)
        search_frame.setStyleSheet(
            "background:#13151a;border-bottom:1px solid #2d3340;"
        )
        sl = QHBoxLayout(search_frame)
        sl.setContentsMargins(8, 5, 8, 5)
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Cari layer…")
        self._search.setFixedHeight(28)
        self._search.setStyleSheet(
            "background:#0f1116;border:1px solid #2d3340;border-radius:4px;"
            "color:#c0cad8;padding:2px 8px;font-size:11px;"
        )
        self._search.textChanged.connect(self._filter)
        sl.addWidget(self._search)
        layout.addWidget(search_frame)

        # Tree
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._context_menu)
        self._tree.itemClicked.connect(self._on_click)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        self._tree.setStyleSheet("""
            QTreeWidget {background:#13151a;border:none;outline:none;}
            QTreeWidget::item {padding:5px 4px;border-radius:3px;}
            QTreeWidget::item:hover {background:#1e2229;}
            QTreeWidget::item:selected {background:#2e5bff28;color:#6699ff;}
            QTreeWidget::branch {background:#13151a;}
        """)
        layout.addWidget(self._tree, 1)

        # Footer / info
        self._footer = QLabel("  Klik dua kali layer untuk memuat peta")
        self._footer.setWordWrap(True)
        self._footer.setFixedHeight(44)
        self._footer.setStyleSheet(
            "color:#4a5570;font-size:10px;padding:6px 12px;"
            "background:#0f1116;border-top:1px solid #2d3340;"
        )
        layout.addWidget(self._footer)

    # ── Public API ────────────────────────────────────────────────────────────

    def populate(self, layers: List[LayerInfo]):
        """Rebuild the tree from a list of LayerInfo objects."""
        self._layers = layers
        self._tree.clear()
        schemas: dict[str, QTreeWidgetItem] = {}

        spatial_count = 0
        table_count = 0

        for layer in layers:
            # Schema node
            if layer.schema not in schemas:
                schema_item = QTreeWidgetItem([f"📁  {layer.schema}"])
                schema_item.setExpanded(True)
                schema_item.setForeground(0, QColor("#6a7590"))
                schema_item.setFlags(schema_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self._tree.addTopLevelItem(schema_item)
                schemas[layer.schema] = schema_item

            icon = GEOM_ICONS.get(layer.geom_family, "🌐")
            label = f"{icon}  {layer.table_name}"
            if not layer.is_spatial:
                label += "  (tabel)"
            child = QTreeWidgetItem([label])
            child.setData(0, Qt.ItemDataRole.UserRole, layer)
            child.setToolTip(0, layer.tooltip())
            schemas[layer.schema].addChild(child)

            if layer.is_spatial:
                spatial_count += 1
            else:
                table_count += 1

        if spatial_count and table_count:
            footer = f"  {spatial_count} layer spasial, {table_count} tabel"
        elif spatial_count:
            footer = f"  {spatial_count} layer spasial ditemukan"
        elif table_count:
            footer = f"  {table_count} tabel ditemukan"
        else:
            footer = "  Tidak ada layer di database ini"
        self._footer.setText(footer)

    def set_connected(self, connected: bool, label: str = ""):
        self.conn_banner.set_state(connected, label)

    def selected_layer(self) -> Optional[LayerInfo]:
        items = self._tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.ItemDataRole.UserRole)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _on_click(self, item: QTreeWidgetItem, _col: int):
        layer: Optional[LayerInfo] = item.data(0, Qt.ItemDataRole.UserRole)
        if layer:
            if layer.is_spatial:
                self._footer.setText(
                    f"  {layer.table_name}  ·  {layer.geom_type}  ·  SRID:{layer.srid}"
                )
            else:
                self._footer.setText(
                    f"  {layer.table_name}  ·  Tabel  ·  {layer.col_count} kolom"
                )
            self.layer_selected.emit(layer)

    def _on_double_click(self, item: QTreeWidgetItem, _col: int):
        layer: Optional[LayerInfo] = item.data(0, Qt.ItemDataRole.UserRole)
        if layer:
            self.layer_activated.emit(layer)

    def _context_menu(self, pos):
        item = self._tree.itemAt(pos)
        if not item:
            return
        layer: Optional[LayerInfo] = item.data(0, Qt.ItemDataRole.UserRole)
        if not layer:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#1e2229;color:#c0cad8;border:1px solid #2d3340;"
            "border-radius:6px;padding:4px;}"
            "QMenu::item:selected{background:#2e5bff33;border-radius:3px;}"
        )
        
        if layer.is_spatial:
            act_load = menu.addAction("🗺  Tampilkan di Peta")
        act_attr   = menu.addAction("📋  Lihat Atribut")
        menu.addSeparator()
        act_stat   = menu.addAction("📊  Statistik Layer")
        menu.addSeparator()
        act_delete = menu.addAction("🗑  Hapus Tabel dari Database")
        act_delete.setToolTip("DROP TABLE permanen dari PostGIS")

        action = menu.exec(self._tree.viewport().mapToGlobal(pos))
        if layer.is_spatial and action == act_load:
            self.layer_activated.emit(layer)
        elif action == act_attr:
            self.layer_attributes.emit(layer)
        elif action == act_stat:
            self.layer_selected.emit(layer)
        elif action == act_delete:
            self.layer_delete_requested.emit(layer)

    def _filter(self, text: str):
        text = text.lower()
        for i in range(self._tree.topLevelItemCount()):
            schema_item = self._tree.topLevelItem(i)
            any_visible = False
            for j in range(schema_item.childCount()):
                child = schema_item.child(j)
                visible = text in child.text(0).lower()
                child.setHidden(not visible)
                if visible:
                    any_visible = True
            schema_item.setHidden(not any_visible and bool(text))


class _ConnectionBanner(QFrame):
    connect_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet("background:#1e2229;border-bottom:1px solid #2d3340;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)

        self._icon  = QLabel("🔴")
        self._icon.setStyleSheet("font-size:11px;background:transparent;border:none;")
        self._label = QLabel("Belum terhubung")
        self._label.setStyleSheet(
            "color:#6a7590;font-size:11px;background:transparent;border:none;"
        )
        layout.addWidget(self._icon)
        layout.addWidget(self._label, 1)

    def set_state(self, connected: bool, label: str = ""):
        self._icon.setText("🟢" if connected else "🔴")
        self._label.setText(label if label else ("Terhubung" if connected else "Belum terhubung"))
        self._label.setStyleSheet(
            f"font-size:11px;background:transparent;border:none;"
            f"color:{'#1e9e6a' if connected else '#6a7590'};"
        )
