"""
dialogs/pipeline_dialog.py
Visual Pipeline Builder — drag & drop node editor.

Layout:
┌──────────────────────────────────────────────────────────────────┐
│  Toolbar: [+Source] [+Query] [+Geoprocess] [+Output]  [▶ Run]   │
├────────────────┬─────────────────────────────────────────────────┤
│                │                                                  │
│  NODE PALETTE  │           PIPELINE CANVAS                       │
│  (left panel)  │   (QGraphicsScene — drag nodes, draw edges)     │
│                │                                                  │
├────────────────┴─────────────────────────────────────────────────┤
│  PROPERTIES PANEL (bottom): edit selected node params            │
├──────────────────────────────────────────────────────────────────┤
│  LOG / STATUS                                                     │
└──────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import (
    Qt, pyqtSignal, QPointF, QRectF, QLineF,
    QTimer,
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
    QKeySequence,
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QFrame, QScrollArea, QWidget,
    QTextEdit, QLineEdit, QComboBox, QDoubleSpinBox,
    QSpinBox, QCheckBox, QFormLayout, QGroupBox,
    QFileDialog, QMessageBox, QApplication, QSizePolicy,
    QGraphicsScene, QGraphicsView, QGraphicsItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
    QGraphicsEllipseItem, QMenu, QTabWidget,
)

from core.pipeline.model import Pipeline, PipelineNode, PipelineEdge, NODE_TYPES
from core.pipeline.executor import PipelineExecutor
from core.geoprocessing.factory import GeoprocessFactory
from utils.constants import SPATIAL_PREDICATES, JOIN_TYPES, AREA_UNITS, COMMON_SRID
from utils.logger import get_logger

logger = get_logger("spaque.dialogs.pipeline")

# ── Colors ─────────────────────────────────────────────────────────────────────
NODE_COLORS = {
    "source":     ("#1e4a2a", "#2e9e5a", "#e0ffe8"),
    "query":      ("#1e2a4a", "#2e5bff", "#e0e8ff"),
    "geoprocess": ("#2a1e4a", "#7e3eff", "#ede0ff"),
    "output":     ("#4a2a1e", "#ff7e3e", "#ffe8e0"),
}
EDGE_COLOR  = QColor("#4a5570")
EDGE_HOVER  = QColor("#2e5bff")


# ── Graphics Items ─────────────────────────────────────────────────────────────

class NodeItem(QGraphicsRectItem):
    """A draggable node on the canvas."""

    WIDTH  = 180
    HEIGHT = 60

    def __init__(self, node: PipelineNode, scene: "PipelineScene"):
        super().__init__(0, 0, self.WIDTH, self.HEIGHT)
        self.node   = node
        self._scene = scene
        self.setPos(node.x, node.y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._hovered = False
        self._update_style()

        # Label text
        self._text = QGraphicsTextItem(node.label, self)
        self._text.setDefaultTextColor(QColor(NODE_COLORS[node.node_type][2]))
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self._text.setFont(font)
        self._center_text()

        # Port circles (input/output)
        self._in_port  = QGraphicsEllipseItem(-8, self.HEIGHT//2-8, 16, 16, self)
        self._out_port = QGraphicsEllipseItem(self.WIDTH-8, self.HEIGHT//2-8, 16, 16, self)
        port_brush = QBrush(QColor("#2d3340"))
        port_pen   = QPen(QColor("#6a7590"), 1.5)
        for p in (self._in_port, self._out_port):
            p.setBrush(port_brush)
            p.setPen(port_pen)
            p.setZValue(2)

        # Hide input port for source nodes
        if node.node_type == "source":
            self._in_port.setVisible(False)
        # Hide output port for output nodes
        if node.node_type == "output":
            self._out_port.setVisible(False)

    def refresh_label(self):
        self._text.setPlainText(self.node.label)
        self._center_text()

    def _center_text(self):
        br = self._text.boundingRect()
        self._text.setPos(
            (self.WIDTH - br.width()) / 2,
            (self.HEIGHT - br.height()) / 2,
        )

    def _update_style(self):
        bg, border, _ = NODE_COLORS.get(self.node.node_type, ("#1e2229","#2d3340","#c0cad8"))
        pen_color = EDGE_HOVER if (self._hovered or self.isSelected()) else QColor(border)
        pen_width = 2.5 if (self._hovered or self.isSelected()) else 1.5
        self.setBrush(QBrush(QColor(bg)))
        self.setPen(QPen(pen_color, pen_width))
        self.setZValue(1)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self._update_style()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self._update_style()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.node.x = self.x()
            self.node.y = self.y()
            self._scene.update_edges()
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._update_style()
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        menu = QMenu()
        menu.setStyleSheet(
            "QMenu{background:#1e2229;color:#c0cad8;border:1px solid #2d3340;"
            "border-radius:6px;padding:4px;}"
            "QMenu::item:selected{background:#2e5bff33;border-radius:3px;}"
        )
        edit_act   = menu.addAction("✏  Edit Parameter")
        menu.addSeparator()
        delete_act = menu.addAction("🗑  Hapus Node")
        action = menu.exec(event.screenPos())
        if action == delete_act:
            self._scene.remove_node(self.node.node_id)
        elif action == edit_act:
            self._scene.request_edit(self.node.node_id)

    def out_port_center(self) -> QPointF:
        return self.mapToScene(QPointF(self.WIDTH + 0, self.HEIGHT / 2))

    def in_port_center(self) -> QPointF:
        return self.mapToScene(QPointF(0, self.HEIGHT / 2))


class EdgeItem(QGraphicsItem):
    """An arrow connecting two nodes."""

    def __init__(self, from_node: NodeItem, to_node: NodeItem):
        super().__init__()
        self.from_node = from_node
        self.to_node   = to_node
        self.setZValue(0)

    def boundingRect(self) -> QRectF:
        p1 = self.from_node.out_port_center()
        p2 = self.to_node.in_port_center()
        return QRectF(p1, p2).normalized().adjusted(-20, -20, 20, 20)

    def paint(self, painter: QPainter, option, widget=None):
        p1 = self.from_node.out_port_center()
        p2 = self.to_node.in_port_center()

        # Bezier curve
        path = QPainterPath(p1)
        dx = abs(p2.x() - p1.x()) * 0.5
        path.cubicTo(
            p1.x() + dx, p1.y(),
            p2.x() - dx, p2.y(),
            p2.x(), p2.y(),
        )
        painter.setPen(QPen(EDGE_COLOR, 2, Qt.PenStyle.SolidLine,
                             Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Arrow head
        line = QLineF(p1, p2)
        if line.length() < 1:
            return
        angle = line.angle()
        painter.setPen(QPen(EDGE_COLOR, 2))
        painter.setBrush(QBrush(EDGE_COLOR))
        # Simple arrow tip
        import math
        a = math.radians(angle)
        tip = p2
        arr_len = 12
        left  = QPointF(
            tip.x() + arr_len * math.cos(a + math.radians(150)),
            tip.y() - arr_len * math.sin(a + math.radians(150)),
        )
        right = QPointF(
            tip.x() + arr_len * math.cos(a - math.radians(150)),
            tip.y() - arr_len * math.sin(a - math.radians(150)),
        )
        arrow = QPainterPath()
        arrow.moveTo(tip)
        arrow.lineTo(left)
        arrow.lineTo(right)
        arrow.closeSubpath()
        painter.drawPath(arrow)


# ── Pipeline Scene ─────────────────────────────────────────────────────────────

class PipelineScene(QGraphicsScene):
    node_selected    = pyqtSignal(str)     # node_id
    selection_cleared = pyqtSignal()
    pipeline_changed = pyqtSignal()

    def __init__(self, pipeline: Pipeline, parent=None):
        super().__init__(parent)
        self.pipeline      = pipeline
        self._node_items:  Dict[str, NodeItem]  = {}
        self._edge_items:  List[EdgeItem]        = []
        self._draw_edge_from: Optional[NodeItem] = None

        self.setBackgroundBrush(QBrush(QColor("#13151a")))
        self._rebuild()

    def _rebuild(self):
        self.clear()
        self._node_items.clear()
        self._edge_items.clear()

        for node in self.pipeline.nodes:
            self._add_node_item(node)
        for edge in self.pipeline.edges:
            self._add_edge_item(edge.from_id, edge.to_id)

    def _add_node_item(self, node: PipelineNode) -> NodeItem:
        item = NodeItem(node, self)
        self.addItem(item)
        self._node_items[node.node_id] = item
        return item

    def _add_edge_item(self, from_id: str, to_id: str):
        fi = self._node_items.get(from_id)
        ti = self._node_items.get(to_id)
        if fi and ti:
            ei = EdgeItem(fi, ti)
            self.addItem(ei)
            self._edge_items.append(ei)

    def add_node(self, node: PipelineNode):
        self.pipeline.add_node(node)
        self._add_node_item(node)
        self.pipeline_changed.emit()

    def remove_node(self, node_id: str):
        self.pipeline.remove_node(node_id)
        self._rebuild()
        self.pipeline_changed.emit()
        self.selection_cleared.emit()

    def request_edit(self, node_id: str):
        self.node_selected.emit(node_id)

    def update_edges(self):
        for ei in self._edge_items:
            ei.prepareGeometryChange()
            ei.update()

    def connect_nodes(self, from_id: str, to_id: str) -> bool:
        ok = self.pipeline.add_edge(from_id, to_id)
        if ok:
            self._add_edge_item(from_id, to_id)
            self.pipeline_changed.emit()
        return ok

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        items = self.selectedItems()
        if items and isinstance(items[0], NodeItem):
            self.node_selected.emit(items[0].node.node_id)
        else:
            self.selection_cleared.emit()

    def refresh_node_label(self, node_id: str):
        item = self._node_items.get(node_id)
        if item:
            item.refresh_label()


# ── Worker thread ──────────────────────────────────────────────────────────────

class _SyncProgressCallback:
    """
    Wrapper progress callback yang memanggil processEvents() agar
    UI log panel terupdate saat pipeline berjalan synchronous.
    """
    def __init__(self, log_fn):
        self._log = log_fn

    def __call__(self, msg: str):
        self._log(msg)
        QApplication.processEvents()


# ── Main Dialog ────────────────────────────────────────────────────────────────

class PipelineDialog(QDialog):
    """Visual Pipeline Builder dialog."""

    pipeline_executed = pyqtSignal(object)   # PipelineResult

    def __init__(self, layers, get_columns, repo=None, parent=None):
        super().__init__(parent)
        self._layers     = layers
        self._get_cols   = get_columns
        self._repo       = repo
        self._pipeline   = Pipeline(name="Pipeline Baru")
        self._scene: Optional[PipelineScene] = None

        self.setWindowTitle("Visual Pipeline Builder")
        self.resize(1100, 720)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self._build_ui()
        self._init_scene()

    # ── UI Assembly ────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header toolbar
        root.addWidget(self._build_header())

        # Main splitter: canvas | props
        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.setHandleWidth(2)
        main_split.setStyleSheet("QSplitter::handle{background:#2d3340;}")

        # Left: palette + canvas stacked vertically
        left_split = QSplitter(Qt.Orientation.Vertical)
        left_split.setHandleWidth(2)
        left_split.setStyleSheet("QSplitter::handle{background:#2d3340;}")
        left_split.addWidget(self._build_palette())
        left_split.addWidget(self._build_canvas_frame())
        left_split.setSizes([160, 500])

        main_split.addWidget(left_split)
        main_split.addWidget(self._build_props_panel())
        main_split.setSizes([750, 330])

        # Vertical split: canvas area | log
        outer_split = QSplitter(Qt.Orientation.Vertical)
        outer_split.setHandleWidth(2)
        outer_split.setStyleSheet("QSplitter::handle{background:#2d3340;}")
        outer_split.addWidget(main_split)
        outer_split.addWidget(self._build_log_panel())
        outer_split.setSizes([560, 120])

        root.addWidget(outer_split, 1)

    def _build_header(self) -> QFrame:
        hdr = QFrame()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #0f1116,stop:1 #1a1d23);"
            "border-bottom:1px solid #2d3340;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 6, 12, 6)
        hl.setSpacing(6)

        # Title
        icon  = QLabel("🔀")
        icon.setStyleSheet("font-size:20px;background:transparent;border:none;")
        title = QLabel("Visual Pipeline Builder")
        title.setStyleSheet(
            "font-size:14px;font-weight:bold;color:#e0e6f0;"
            "background:transparent;border:none;"
        )
        hl.addWidget(icon)
        hl.addWidget(title)
        hl.addStretch()

        # Pipeline name
        name_lbl = QLabel("Nama:")
        name_lbl.setStyleSheet("color:#6a7590;font-size:11px;background:transparent;border:none;")
        self._name_edit = QLineEdit(self._pipeline.name)
        self._name_edit.setFixedHeight(28)
        self._name_edit.setFixedWidth(200)
        self._name_edit.setStyleSheet("font-size:11px;")
        self._name_edit.textChanged.connect(lambda t: setattr(self._pipeline, 'name', t))
        hl.addWidget(name_lbl)
        hl.addWidget(self._name_edit)

        def sep():
            return self._vsep()

        # Action buttons
        hl.addWidget(sep())

        def btn(label, slot, tip="", obj=""):
            b = QPushButton(label)
            b.setFixedHeight(32)
            b.setToolTip(tip)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(slot)
            hl.addWidget(b)
            return b

        btn("📂 Buka",  self._load_pipeline, "Buka pipeline dari file (.json)")
        btn("💾 Simpan", self._save_pipeline, "Simpan pipeline ke file (.json)")
        hl.addWidget(sep())
        btn("🗑 Reset",  self._reset_pipeline, "Buat pipeline baru kosong")
        hl.addWidget(sep())
        self._run_btn = btn("▶  Jalankan Pipeline", self._run_pipeline,
                             "Jalankan semua node secara berurutan", "success")
        btn("✕ Tutup", self.reject)

        return hdr

    def _vsep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet("background:#2d3340;max-width:1px;margin:4px 4px;")
        return f

    def _build_palette(self) -> QFrame:
        """Left palette: drag-to-add node types."""
        frame = QFrame()
        frame.setFixedWidth(200)
        frame.setStyleSheet("background:#13151a;border-right:1px solid #2d3340;")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        hdr = QLabel("  TAMBAH NODE")
        hdr.setFixedHeight(32)
        hdr.setStyleSheet(
            "color:#6a7590;font-size:9px;font-weight:bold;letter-spacing:1px;"
            "background:#0f1116;border-bottom:1px solid #2d3340;padding-left:10px;"
        )
        fl.addWidget(hdr)

        hint = QLabel(
            "  Klik tombol di bawah\n  untuk menambah node\n  ke pipeline."
        )
        hint.setStyleSheet(
            "color:#3d4455;font-size:10px;padding:8px 10px;background:transparent;"
        )
        fl.addWidget(hint)

        for node_type, (icon, label, bg) in NODE_TYPES.items():
            _, border, fg = NODE_COLORS.get(node_type, ("#1e2229","#2d3340","#c0cad8"))
            b = QPushButton(f"{icon}  {label}")
            b.setFixedHeight(38)
            b.setStyleSheet(f"""
                QPushButton {{
                    background:#1a1d23;color:{fg};
                    border:1px solid {border};border-radius:6px;
                    margin:4px 8px;font-size:11px;font-weight:600;text-align:left;
                    padding-left:10px;
                }}
                QPushButton:hover {{ background:{border}33; }}
                QPushButton:pressed {{ background:{border}55; }}
            """)
            b.setToolTip(f"Tambahkan node {label} ke pipeline")
            b.clicked.connect(lambda _, nt=node_type: self._add_node(nt))
            fl.addWidget(b)

        fl.addStretch()

        # Mini instructions
        guide = QLabel(
            "  📌 Tips:\n"
            "  • Klik node → edit params\n"
            "  • Kanan-klik → hapus/edit\n"
            "  • Sambungkan node via\n"
            "    tombol 'Sambungkan'\n"
            "  di panel kanan"
        )
        guide.setStyleSheet(
            "color:#3d4455;font-size:10px;padding:8px 10px;background:transparent;"
            "line-height:1.4;"
        )
        fl.addWidget(guide)
        return frame

    def _build_canvas_frame(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("background:#13151a;")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        canvas_hdr = QFrame()
        canvas_hdr.setFixedHeight(30)
        canvas_hdr.setStyleSheet(
            "background:#0f1116;border-bottom:1px solid #2d3340;"
        )
        ch = QHBoxLayout(canvas_hdr)
        ch.setContentsMargins(10, 0, 10, 0)
        lbl = QLabel("🎨  KANVAS PIPELINE")
        lbl.setStyleSheet("color:#6a7590;font-size:9px;font-weight:bold;letter-spacing:1px;background:transparent;border:none;")
        ch.addWidget(lbl)
        ch.addStretch()

        # Connect nodes button
        self._from_combo = QComboBox()
        self._from_combo.setFixedHeight(22)
        self._from_combo.setFixedWidth(130)
        self._from_combo.setStyleSheet("font-size:10px;")
        arrow = QLabel("→")
        arrow.setStyleSheet("color:#6a7590;background:transparent;border:none;")
        self._to_combo = QComboBox()
        self._to_combo.setFixedHeight(22)
        self._to_combo.setFixedWidth(130)
        self._to_combo.setStyleSheet("font-size:10px;")
        conn_btn = QPushButton("Sambungkan")
        conn_btn.setFixedHeight(22)
        conn_btn.setObjectName("secondary")
        conn_btn.setStyleSheet("font-size:10px;padding:2px 8px;")
        conn_btn.clicked.connect(self._connect_selected_nodes)
        ch.addWidget(QLabel("  Sambungkan:"))
        ch.addWidget(self._from_combo)
        ch.addWidget(arrow)
        ch.addWidget(self._to_combo)
        ch.addWidget(conn_btn)
        fl.addWidget(canvas_hdr)

        # Graphics view
        self._view = QGraphicsView()
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self._view.setStyleSheet("QGraphicsView{border:none;background:#13151a;}")
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        fl.addWidget(self._view, 1)
        return frame

    def _build_props_panel(self) -> QFrame:
        frame = QFrame()
        frame.setFixedWidth(330)
        frame.setStyleSheet("background:#1a1d23;border-left:1px solid #2d3340;")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)

        hdr = QLabel("  PROPERTI NODE")
        hdr.setFixedHeight(32)
        hdr.setStyleSheet(
            "color:#6a7590;font-size:9px;font-weight:bold;letter-spacing:1px;"
            "background:#0f1116;border-bottom:1px solid #2d3340;padding-left:10px;"
        )
        fl.addWidget(hdr)

        # Scrollable props area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:#1a1d23;}")
        self._props_container = QWidget()
        self._props_container.setStyleSheet("background:#1a1d23;")
        self._props_layout = QVBoxLayout(self._props_container)
        self._props_layout.setContentsMargins(12, 12, 12, 12)
        self._props_layout.setSpacing(8)

        self._props_hint = QLabel("← Klik node di kanvas untuk\n   mengedit parameternya")
        self._props_hint.setStyleSheet("color:#4a5570;font-size:11px;")
        self._props_layout.addWidget(self._props_hint)
        self._props_layout.addStretch()

        scroll.setWidget(self._props_container)
        fl.addWidget(scroll, 1)
        return frame

    def _build_log_panel(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            "background:#0f1116;border-top:1px solid #2d3340;"
        )
        fl = QHBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("  📜 LOG")
        lbl.setFixedWidth(60)
        lbl.setStyleSheet(
            "color:#6a7590;font-size:9px;font-weight:bold;letter-spacing:1px;"
            "background:transparent;padding-left:8px;"
        )
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(100)
        self._log.setStyleSheet(
            "background:#0f1116;color:#a0aab8;font-family:monospace;"
            "font-size:10px;border:none;padding:4px;"
        )
        fl.addWidget(lbl)
        fl.addWidget(self._log, 1)
        return frame

    # ── Scene init ─────────────────────────────────────────────────────────────

    def _init_scene(self):
        self._scene = PipelineScene(self._pipeline)
        self._scene.node_selected.connect(self._on_node_selected)
        self._scene.selection_cleared.connect(self._on_selection_cleared)
        self._scene.pipeline_changed.connect(self._refresh_combos)
        self._view.setScene(self._scene)
        self._refresh_combos()

    def _refresh_combos(self):
        """Update the From/To node combos."""
        for cb in (self._from_combo, self._to_combo):
            cb.blockSignals(True)
            cb.clear()
            for node in self._pipeline.nodes:
                cb.addItem(node.label, node.node_id)
            cb.blockSignals(False)

    # ── Node management ────────────────────────────────────────────────────────

    def _add_node(self, node_type: str):
        # Place at reasonable offset
        existing = len(self._pipeline.nodes)
        x = 60 + (existing % 4) * 220
        y = 80 + (existing // 4) * 120

        node = PipelineNode.new(node_type, x=float(x), y=float(y))

        # Pre-fill defaults
        if node_type == "source" and self._layers:
            layer = self._layers[0]
            node.params["schema"]   = layer.schema
            node.params["table"]    = layer.table_name
            node.params["geom_col"] = layer.geom_col
            node.params["limit"]    = 5000
        elif node_type == "query" and self._layers:
            layer = self._layers[0]
            node.params["schema"] = layer.schema
            node.params["table"]  = layer.table_name
            node.params["conditions"] = []
        elif node_type == "geoprocess":
            # Pre-fill input from first layer
            if self._layers:
                first = self._layers[0]
                node.params["input_schema"] = first.schema
                node.params["input_table"]  = first.table_name
                node.params["input_geom"]   = first.geom_col
            node.params["operation"]     = "Buffer"
            node.params["output_table"]  = "hasil_pipeline"
            node.params["output_schema"] = "public"
            node.params["distance"]      = 100.0
            node.params["segments"]      = 16
        elif node_type == "output":
            node.params["output_table"]  = "pipeline_output"
            node.params["output_schema"] = "public"

        self._scene.add_node(node)
        self._log_msg(f"Node '{node.label}' ditambahkan")

    def _connect_selected_nodes(self):
        from_id = self._from_combo.currentData()
        to_id   = self._to_combo.currentData()
        if not from_id or not to_id:
            return
        if from_id == to_id:
            self._log_msg("❌ Tidak bisa menyambung node ke dirinya sendiri")
            return
        ok = self._scene.connect_nodes(from_id, to_id)
        if ok:
            fn = self._pipeline.node_by_id(from_id)
            tn = self._pipeline.node_by_id(to_id)
            self._log_msg(f"✅ Terhubung: {fn.label} → {tn.label}")
        else:
            self._log_msg("❌ Koneksi sudah ada atau tidak valid")

    # ── Properties panel ───────────────────────────────────────────────────────

    def _on_node_selected(self, node_id: str):
        node = self._pipeline.node_by_id(node_id)
        if not node:
            return
        self._show_node_props(node)

    def _on_selection_cleared(self):
        self._clear_props()

    def _clear_props(self):
        while self._props_layout.count():
            item = self._props_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._props_hint = QLabel("← Klik node di kanvas untuk\n   mengedit parameternya")
        self._props_hint.setStyleSheet("color:#4a5570;font-size:11px;")
        self._props_layout.addWidget(self._props_hint)
        self._props_layout.addStretch()

    def _lbl(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#6a7590;font-size:11px;font-weight:600;")
        return lbl

    def _show_node_props(self, node: PipelineNode):
        """Build form widgets for a node."""
        while self._props_layout.count():
            item = self._props_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Node type badge
        icon, label, bg = NODE_TYPES.get(node.node_type, ("⚙", node.node_type, "#1e2229"))
        _, border, fg = NODE_COLORS.get(node.node_type, ("#1e2229","#2d3340","#c0cad8"))
        badge = QLabel(f"  {icon}  {label}  ")
        badge.setStyleSheet(f"""
            background:{bg};color:{fg};border:1px solid {border};
            border-radius:4px;font-weight:700;font-size:11px;padding:4px 0;
        """)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._props_layout.addWidget(badge)

        node_id_lbl = QLabel(f"ID: {node.node_id}")
        node_id_lbl.setStyleSheet("color:#3d4455;font-size:9px;")
        self._props_layout.addWidget(node_id_lbl)

        # Build type-specific form
        if node.node_type == "source":
            self._props_source(node)
        elif node.node_type == "query":
            self._props_query(node)
        elif node.node_type == "geoprocess":
            self._props_geoprocess(node)
        elif node.node_type == "output":
            self._props_output(node)

        self._props_layout.addStretch()

    def _section_grp(self, title: str) -> QGroupBox:
        g = QGroupBox(title)
        g.setStyleSheet("""
            QGroupBox {
                border:1px solid #2d3340;border-radius:6px;
                margin-top:8px;padding:8px 8px 6px;
                color:#6a7590;font-weight:700;font-size:10px;
            }
            QGroupBox::title {subcontrol-origin:margin;left:8px;padding:0 4px;}
        """)
        return g

    def _props_source(self, node: PipelineNode):
        grp = self._section_grp("Data Source")
        form = QFormLayout(grp)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        layer_items = [f"{lyr.schema}.{lyr.table_name}" for lyr in self._layers]
        layer_cb = QComboBox()
        layer_cb.setFixedHeight(28)
        layer_cb.addItems(layer_items)

        # Set current
        cur = f"{node.params.get('schema','public')}.{node.params.get('table','')}"
        if cur in layer_items:
            layer_cb.setCurrentText(cur)

        def on_layer_changed(text):
            parts = text.split(".", 1)
            if len(parts) == 2:
                node.params["schema"] = parts[0]
                node.params["table"]  = parts[1]
            # Find geom_col
            for layer in self._layers:
                if layer.schema == node.params.get("schema") \
                        and layer.table_name == node.params.get("table"):
                    node.params["geom_col"] = layer.geom_col
                    break
            self._scene.refresh_node_label(node.node_id)

        layer_cb.currentTextChanged.connect(on_layer_changed)
        form.addRow(self._lbl("Layer:"), layer_cb)

        limit_spin = QSpinBox()
        limit_spin.setRange(100, 500000)
        limit_spin.setValue(int(node.params.get("limit", 5000)))
        limit_spin.setFixedHeight(28)
        limit_spin.setSuffix(" fitur")
        limit_spin.valueChanged.connect(lambda v: node.params.update({"limit": v}))
        form.addRow(self._lbl("Limit:"), limit_spin)
        self._props_layout.addWidget(grp)

    def _props_query(self, node: PipelineNode):
        grp = self._section_grp("Query Filter (WHERE)")
        form = QFormLayout(grp)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        layer_items = [f"{lyr.schema}.{lyr.table_name}" for lyr in self._layers]
        layer_cb = QComboBox()
        layer_cb.setFixedHeight(28)
        layer_cb.addItems(layer_items)
        cur = f"{node.params.get('schema','public')}.{node.params.get('table','')}"
        if cur in layer_items:
            layer_cb.setCurrentText(cur)

        def on_layer_chg(text):
            parts = text.split(".", 1)
            if len(parts) == 2:
                node.params["schema"] = parts[0]
                node.params["table"]  = parts[1]

        layer_cb.currentTextChanged.connect(on_layer_chg)
        form.addRow(self._lbl("Tabel:"), layer_cb)

        # WHERE clause as raw text (simple mode)
        where_edit = QTextEdit()
        where_edit.setFixedHeight(60)
        where_edit.setPlaceholderText('Contoh: "luas" > 1000\nAND "n_kh" = \'HL\'')
        where_edit.setStyleSheet(
            "background:#0f1116;color:#7adb78;font-family:monospace;"
            "font-size:10px;border:1px solid #2d3340;border-radius:4px;"
        )
        raw = node.params.get("where_raw", "")
        where_edit.setPlainText(raw)

        def on_where_chg():
            node.params["where_raw"] = where_edit.toPlainText().strip()

        where_edit.textChanged.connect(on_where_chg)
        form.addRow(self._lbl("WHERE:"), where_edit)

        # ORDER + LIMIT
        order_edit = QLineEdit(node.params.get("order_col", ""))
        order_edit.setFixedHeight(26)
        order_edit.setPlaceholderText("kolom (opsional)")
        order_edit.textChanged.connect(lambda t: node.params.update({"order_col": t}))
        form.addRow(self._lbl("Order By:"), order_edit)

        order_dir = QComboBox()
        order_dir.addItems(["ASC", "DESC"])
        order_dir.setFixedHeight(26)
        order_dir.setCurrentText(node.params.get("order_dir", "ASC"))
        order_dir.currentTextChanged.connect(lambda t: node.params.update({"order_dir": t}))
        form.addRow(self._lbl("Arah:"), order_dir)

        limit_spin = QSpinBox()
        limit_spin.setRange(0, 500000)
        limit_spin.setValue(int(node.params.get("limit", 0)))
        limit_spin.setFixedHeight(26)
        limit_spin.setSpecialValueText("semua")
        limit_spin.valueChanged.connect(lambda v: node.params.update({"limit": v}))
        form.addRow(self._lbl("Limit:"), limit_spin)

        self._props_layout.addWidget(grp)

        # SQL preview
        sql_grp = self._section_grp("Preview SQL")
        sg = QVBoxLayout(sql_grp)
        sql_view = QTextEdit()
        sql_view.setReadOnly(True)
        sql_view.setFixedHeight(70)
        sql_view.setStyleSheet(
            "background:#0f1116;color:#7adb78;font-family:monospace;"
            "font-size:10px;border:1px solid #2d3340;border-radius:4px;"
        )

        def update_sql():
            schema = node.params.get("schema", "public")
            table  = node.params.get("table", "")
            where  = node.params.get("where_raw", "").strip()
            order  = node.params.get("order_col", "").strip()
            order_d= node.params.get("order_dir", "ASC")
            limit  = node.params.get("limit", 0)
            parts  = [f'SELECT *\nFROM "{schema}"."{table}"']
            if where:
                parts.append(f"WHERE {where}")
            if order:
                parts.append(f'ORDER BY "{order}" {order_d}')
            if limit:
                parts.append(f"LIMIT {limit}")
            sql_view.setPlainText("\n".join(parts))

        update_sql()
        where_edit.textChanged.connect(update_sql)
        order_edit.textChanged.connect(update_sql)
        order_dir.currentTextChanged.connect(update_sql)
        limit_spin.valueChanged.connect(update_sql)
        sg.addWidget(sql_view)
        self._props_layout.addWidget(sql_grp)

    def _props_geoprocess(self, node: PipelineNode):
        grp = self._section_grp("Geoprocessing")
        form = QFormLayout(grp)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        layer_items    = [f"{lyr.schema}.{lyr.table_name}" for lyr in self._layers]
        layer_items_ov = ["(tidak ada)"] + layer_items

        # ── Operasi ────────────────────────────────────────────────────────────
        op_cb = QComboBox()
        op_cb.setFixedHeight(28)
        for op in GeoprocessFactory.all_operations():
            op_cb.addItem(f"{op.icon} {op.name}", op.name)
        cur_op = node.params.get("operation", "Buffer")
        idx = op_cb.findData(cur_op)
        if idx >= 0:
            op_cb.setCurrentIndex(idx)
        op_cb.currentIndexChanged.connect(
            lambda _: node.params.update({"operation": op_cb.currentData()})
        )
        form.addRow(self._lbl("Operasi:"), op_cb)

        # ── Layer Input (eksplisit — ini yang jadi input_schema/input_table) ──
        inp_cb = QComboBox()
        inp_cb.setFixedHeight(28)
        inp_cb.addItems(layer_items)

        # Restore current input
        cur_inp = (f"{node.params.get('input_schema','')}"
                   f".{node.params.get('input_table','')}")
        if cur_inp in layer_items:
            inp_cb.setCurrentText(cur_inp)
        elif layer_items:
            # Auto-fill from first layer if not yet set
            parts = layer_items[0].split(".", 1)
            if len(parts) == 2 and not node.params.get("input_table"):
                node.params["input_schema"] = parts[0]
                node.params["input_table"]  = parts[1]
                node.params["input_geom"]   = next(
                    (lyr.geom_col for lyr in self._layers
                     if lyr.schema == parts[0] and lyr.table_name == parts[1]), "geom")

        def on_inp_chg(text):
            parts = text.split(".", 1)
            if len(parts) == 2:
                node.params["input_schema"] = parts[0]
                node.params["input_table"]  = parts[1]
                node.params["input_geom"]   = next(
                    (lyr.geom_col for lyr in self._layers
                     if lyr.schema == parts[0] and lyr.table_name == parts[1]), "geom")

        inp_cb.currentTextChanged.connect(on_inp_chg)
        form.addRow(self._lbl("Layer Input:"), inp_cb)

        # ── Layer Overlay ──────────────────────────────────────────────────────
        ov_cb = QComboBox()
        ov_cb.setFixedHeight(28)
        ov_cb.addItems(layer_items_ov)

        # Restore current overlay
        cur_ov = (f"{node.params.get('overlay_schema','')}"
                  f".{node.params.get('overlay_table','')}")
        if cur_ov in layer_items_ov:
            ov_cb.setCurrentText(cur_ov)
        else:
            ov_cb.setCurrentIndex(0)   # "(tidak ada)"

        def on_ov_chg(text):
            if text == "(tidak ada)":
                node.params.pop("overlay_schema", None)
                node.params.pop("overlay_table",  None)
                node.params.pop("overlay_geom",   None)
            else:
                parts = text.split(".", 1)
                if len(parts) == 2:
                    node.params["overlay_schema"] = parts[0]
                    node.params["overlay_table"]  = parts[1]
                    node.params["overlay_geom"]   = next(
                        (lyr.geom_col for lyr in self._layers
                         if lyr.schema == parts[0] and lyr.table_name == parts[1]), "geom")

        ov_cb.currentTextChanged.connect(on_ov_chg)
        form.addRow(self._lbl("Layer Overlay:"), ov_cb)

        # Hint: overlay wajib untuk operasi tertentu
        ov_hint = QLabel(
            "💡 Overlay diperlukan untuk: Clip, Intersect,\n"
            "   Difference, Spatial Join, Select by Location, dll."
        )
        ov_hint.setStyleSheet("color:#4a5570;font-size:9px;")
        form.addRow("", ov_hint)

        # ── Jarak ──────────────────────────────────────────────────────────────
        dist_spin = QDoubleSpinBox()
        dist_spin.setRange(0.001, 999999)
        dist_spin.setValue(float(node.params.get("distance", 100)))
        dist_spin.setDecimals(1)
        dist_spin.setFixedHeight(28)
        dist_spin.setSuffix(" m")
        dist_spin.valueChanged.connect(lambda v: node.params.update({"distance": v}))
        form.addRow(self._lbl("Jarak (m):"), dist_spin)

        # ── Dissolve ───────────────────────────────────────────────────────────
        dissolve_cb = QCheckBox("Dissolve hasil")
        dissolve_cb.setChecked(bool(node.params.get("dissolve", False)))
        dissolve_cb.setStyleSheet("color:#c0cad8;font-size:11px;")
        dissolve_cb.toggled.connect(lambda v: node.params.update({"dissolve": v}))
        form.addRow(self._lbl(""), dissolve_cb)

        self._props_layout.addWidget(grp)

        # ── Output ─────────────────────────────────────────────────────────────
        out_grp = self._section_grp("Output")
        of = QFormLayout(out_grp)
        of.setSpacing(8)
        of.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        out_edit = QLineEdit(node.params.get("output_table", "hasil_pipeline"))
        out_edit.setFixedHeight(28)
        out_edit.textChanged.connect(lambda t: node.params.update({"output_table": t}))
        of.addRow(self._lbl("Tabel output:"), out_edit)

        sch_edit = QLineEdit(node.params.get("output_schema", "public"))
        sch_edit.setFixedHeight(28)
        sch_edit.textChanged.connect(lambda t: node.params.update({"output_schema": t}))
        of.addRow(self._lbl("Schema:"), sch_edit)

        # SQL preview
        sql_view = QTextEdit()
        sql_view.setReadOnly(True)
        sql_view.setFixedHeight(80)
        sql_view.setStyleSheet(
            "background:#0f1116;color:#7adb78;font-family:monospace;"
            "font-size:10px;border:1px solid #2d3340;border-radius:4px;"
        )

        def update_sql_preview():
            op_name = op_cb.currentData() or ""
            inp     = inp_cb.currentText()
            ov      = ov_cb.currentText()
            out     = out_edit.text() or "hasil"
            if not op_name:
                sql_view.setPlainText("-- Pilih operasi")
                return
            parts = inp.split(".", 1)
            isch  = parts[0] if len(parts) == 2 else "public"
            itbl  = parts[1] if len(parts) == 2 else inp
            ovparts = ov.split(".", 1)
            osch = ovparts[0] if len(ovparts) == 2 else None
            otbl = ovparts[1] if len(ovparts) == 2 else None
            try:
                from core.domain.value_objects import GeoprocessSpec
                from core.geoprocessing.factory import GeoprocessFactory
                op_obj = GeoprocessFactory.get(op_name)
                if op_obj:
                    spec_prev = GeoprocessSpec(
                        operation=op_name,
                        input_schema=isch, input_table=itbl, input_geom="geom",
                        output_table=out, output_schema=sch_edit.text() or "public",
                        overlay_schema=osch, overlay_table=otbl, overlay_geom="geom",
                        distance=dist_spin.value(),
                    )
                    sql_view.setPlainText(op_obj.build_sql(spec_prev))
                else:
                    sql_view.setPlainText(f"-- Operasi '{op_name}' tidak dikenal")
            except Exception as e:
                sql_view.setPlainText(f"-- Error: {e}")

        op_cb.currentIndexChanged.connect(lambda _: update_sql_preview())
        inp_cb.currentTextChanged.connect(lambda _: update_sql_preview())
        ov_cb.currentTextChanged.connect(lambda _: update_sql_preview())
        dist_spin.valueChanged.connect(lambda _: update_sql_preview())
        update_sql_preview()

        of.addRow(self._lbl("Preview SQL:"), sql_view)
        self._props_layout.addWidget(out_grp)

    def _props_output(self, node: PipelineNode):
        grp = self._section_grp("Output Node")
        form = QFormLayout(grp)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        out_edit = QLineEdit(node.params.get("output_table", "pipeline_output"))
        out_edit.setFixedHeight(28)

        def on_out_chg(t):
            node.params["output_table"] = t
            self._scene.refresh_node_label(node.node_id)

        out_edit.textChanged.connect(on_out_chg)
        form.addRow(self._lbl("Nama tabel:"), out_edit)

        sch_edit = QLineEdit(node.params.get("output_schema", "public"))
        sch_edit.setFixedHeight(28)
        sch_edit.textChanged.connect(lambda t: node.params.update({"output_schema": t}))
        form.addRow(self._lbl("Schema:"), sch_edit)

        note = QLabel(
            "💡 Node ini menandai ujung pipeline.\n"
            "Hasil akhir akan tersedia di tabel ini."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#6a7590;font-size:10px;")
        form.addRow("", note)
        self._props_layout.addWidget(grp)

    # ── Pipeline actions ───────────────────────────────────────────────────────

    def _reset_pipeline(self):
        ans = QMessageBox.question(
            self, "Reset Pipeline",
            "Hapus semua node dan mulai pipeline baru?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            self._pipeline = Pipeline(name=self._name_edit.text() or "Pipeline Baru")
            self._scene.pipeline = self._pipeline
            self._scene._rebuild()
            self._refresh_combos()
            self._clear_props()
            self._log_msg("🗑 Pipeline direset")

    def _save_pipeline(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Pipeline", f"{self._pipeline.name}.json",
            "Pipeline JSON (*.json);;Semua File (*.*)"
        )
        if path:
            ok, msg = self._pipeline.save_to_file(path)
            if ok:
                self._log_msg(f"💾 {msg}")
            else:
                QMessageBox.critical(self, "Gagal Simpan", msg)

    def _load_pipeline(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Buka Pipeline", "",
            "Pipeline JSON (*.json);;Semua File (*.*)"
        )
        if not path:
            return
        pipeline, msg = Pipeline.load_from_file(path)
        if not pipeline:
            QMessageBox.critical(self, "Gagal Buka", msg)
            return
        self._pipeline = pipeline
        self._name_edit.setText(pipeline.name)
        self._scene.pipeline = pipeline
        self._scene._rebuild()
        self._refresh_combos()
        self._clear_props()
        self._log_msg(f"📂 {msg}: '{pipeline.name}' ({len(pipeline.nodes)} node)")

    def _run_pipeline(self):
        if not self._repo:
            QMessageBox.warning(self, "Belum Terhubung",
                                "Hubungkan ke database PostGIS terlebih dahulu.")
            return

        errors = self._pipeline.validate()
        if errors:
            QMessageBox.warning(self, "Pipeline Tidak Valid",
                                "\n".join(f"• {e}" for e in errors))
            return

        self._run_btn.setEnabled(False)
        self._log_msg(f"▶ Menjalankan pipeline '{self._pipeline.name}'…")
        QApplication.processEvents()

        # Jalankan synchronous — tidak pakai QThread untuk menghindari
        # segfault akibat race condition saat thread cleanup + Qt object access.
        # processEvents() di callback memastikan UI tetap responsif.
        cb       = _SyncProgressCallback(self._log_msg)
        executor = PipelineExecutor(self._repo, progress_callback=cb)

        try:
            result = executor.run(self._pipeline)
        except Exception as exc:
            self._run_btn.setEnabled(True)
            self._log_msg(f"❌ Exception: {exc}")
            QMessageBox.critical(self, "Pipeline Error", str(exc))
            return

        self._run_btn.setEnabled(True)

        if result.success:
            self._log_msg(f"✅ {result.message}")
            for step in result.steps:
                status = "✅" if step.success else "❌"
                self._log_msg(f"   {status} Node [{step.node_id}]: {step.message}")
            if result.output_table:
                self._log_msg(
                    f"💾 Output: {result.output_schema}.{result.output_table}"
                )
            # Strip GDF sebelum emit — tidak pass object besar antar context
            result.final_gdf = None
            for step in result.steps:
                step.gdf = None
            self.pipeline_executed.emit(result)
        else:
            self._log_msg(f"❌ Pipeline gagal: {result.message}")
            for step in result.steps:
                status = "✅" if step.success else "❌"
                self._log_msg(f"   {status} [{step.node_id}]: {step.message}")
            QMessageBox.critical(self, "Pipeline Gagal", result.message)

    # ── Log ────────────────────────────────────────────────────────────────────

    def _log_msg(self, msg: str):
        self._log.append(msg)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())
        logger.info("[Pipeline] %s", msg)
