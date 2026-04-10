"""
ui/panels/map_canvas.py
Peta interaktif Leaflet.js — FIXED: inline HTML + setHtml(base_url=HTTPS)

Root cause blank map:
  1. folium menggunakan CDN diblokir QWebEngineView (cross-origin dari file://)
  2. load(QUrl.fromLocalFile) tidak memberi akses ke remote resources
  
Solusi:
  - Inject GeoJSON inline sebagai JS variable (tidak butuh fetch)
  - Leaflet dari CDN unpkg.com via setHtml(..., base_url=QUrl("https://..."))
  - QWebEngine setting: LocalContentCanAccessRemoteUrls = True
  - Tidak ada dependency folium sama sekali di render path
"""

from __future__ import annotations

import tempfile
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QComboBox, QPushButton, QSizePolicy,
)

from utils.constants import COLORMAPS
from utils.logger import get_logger

logger = get_logger("spaque.ui.map_canvas")

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    _WEBENGINE_OK = True
except ImportError:
    _WEBENGINE_OK = False
    logger.warning("PyQt6-WebEngine tidak tersedia")


def _get_leaflet_assets() -> tuple[str, str]:
    """
    Return (js_tag, css_tag) untuk Leaflet.
    Prioritas: 1) cached lokal, 2) CDN.
    """
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.leaflet_cache import get_leaflet_js, get_leaflet_css
        js  = get_leaflet_js()
        css = get_leaflet_css()
        if js and css:
            return (
                f"<style>{css}</style>",
                f"<script>{js}</script>",
            )
    except Exception:
        pass
    # Fallback: CDN
    return (
        '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>',
        '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>',
    )


def _build_map_html(geojson_data, center, title, feature_colors,
                    color_stops, vmin, vmax, value_col, count, geom_types):
    geojson_str = __import__("json").dumps(geojson_data, ensure_ascii=False)
    title_safe  = str(title).replace("'", "\\'").replace("<", "&lt;")

    if feature_colors:
        color_js = "var FCOLORS=" + __import__("json").dumps(feature_colors) + ";"
        style_js = """
function sf(f) {
  var c = FCOLORS[f.id] || '#2e5bff';
  var gt = (f.geometry || {}).type || '';
  if (gt.indexOf('Line') >= 0) return {color:c, weight:3, opacity:0.9};
  return {fillColor:c, color:'#ffffff', weight:0.8, fillOpacity:0.8};
}"""
        cs = ','.join(color_stops or ['#440154','#35b779','#fde725'])
        legend = f'''<div style="position:fixed;bottom:30px;right:10px;z-index:9999;
background:rgba(26,29,35,.92);color:#c0cad8;padding:10px 14px;
border-radius:8px;font-family:sans-serif;font-size:11px;border:1px solid #2d3340;min-width:160px;">
<div style="font-weight:700;margin-bottom:6px;color:#e0e6f0;">{value_col}</div>
<div style="display:flex;align-items:center;gap:6px;">
<span>{vmin:.2f}</span>
<div style="flex:1;height:10px;border-radius:5px;
background:linear-gradient(to right,{cs});"></div>
<span>{vmax:.2f}</span></div></div>'''
    else:
        color_js = ""
        style_js = """
function sf(f) {
  var gt = (f.geometry || {}).type || '';
  if (gt.indexOf('Line') >= 0) return {color:'#2e5bff', weight:3, opacity:0.9};
  return {fillColor:'#2e5bff', color:'#ffffff', weight:0.8, fillOpacity:0.7};
}"""
        legend = ""

    title_badge = (
        f'<div style="position:fixed;top:10px;left:50%;transform:translateX(-50%);'
        f'z-index:9999;background:rgba(26,29,35,.92);color:#e0e6f0;padding:6px 18px;'
        f'border-radius:20px;font-family:sans-serif;font-size:13px;font-weight:700;'
        f'border:1px solid #2d3340;pointer-events:none;">📍 {title_safe}</div>'
        if title else ""
    )

    css_tag, js_tag = _get_leaflet_assets()
    return f"""<!DOCTYPE html><html>
<head>
<meta charset="utf-8"/>
{css_tag}
{js_tag}
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:100%;height:100%;background:#1a1d23;}}
#map{{width:100%;height:100%;background:#242830;}}
.leaflet-container{{background:#242830;}}
.leaflet-popup-content-wrapper{{background:#1e2229;color:#c0cad8;border:1px solid #2d3340;}}
.leaflet-popup-tip{{background:#1e2229;}}
.leaflet-popup-content{{color:#c0cad8;font-size:12px;}}
.leaflet-tooltip{{background:#1e2229;border:1px solid #2d3340;color:#c0cad8;
  font-size:11px;border-radius:6px;white-space:nowrap;}}
.leaflet-control-zoom a{{background:#1e2229!important;color:#c0cad8!important;
  border-color:#2d3340!important;}}
.leaflet-control-zoom a:hover{{background:#2d3340!important;}}
.leaflet-control-layers{{background:#1e2229!important;border:1px solid #2d3340!important;}}
.leaflet-control-layers label{{color:#c0cad8;}}
</style>
</head>
<body>
<div id="map"></div>
<div style="position:fixed;bottom:30px;left:10px;z-index:9999;
  background:rgba(26,29,35,.92);color:#6a7590;padding:5px 12px;
  border-radius:8px;font-family:sans-serif;font-size:11px;
  border:1px solid #2d3340;">{count:,} fitur &nbsp;|&nbsp; {geom_types}</div>
{title_badge}
{legend}
<script>
var map = L.map('map').setView([{float(center[0])},{float(center[1])}], 10);
var cartoDark = L.tileLayer(
  'https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',
  {{attribution:'© CARTO', subdomains:'abcd', maxZoom:20}});
var cartoLight = L.tileLayer(
  'https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',
  {{attribution:'© CARTO', subdomains:'abcd', maxZoom:20}});
var osm = L.tileLayer(
  'https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
  {{attribution:'© OpenStreetMap', maxZoom:19}});
cartoDark.addTo(map);

{color_js}
{style_js}

function mkTooltip(p) {{
  if (!p) return '';
  var rows = Object.entries(p).slice(0, 10).map(function(kv) {{
    return '<tr><td style="color:#6a7590;padding-right:10px;white-space:nowrap">'
           + kv[0] + '</td><td style="color:#e0e6f0">' + kv[1] + '</td></tr>';
  }}).join('');
  return '<table style="font-size:11px;border-collapse:collapse">' + rows + '</table>';
}}

var geoData = {geojson_str};

// Pisahkan features berdasarkan tipe geometri
var pointFeatures   = [];
var polygonFeatures = [];
var lineFeatures    = [];

geoData.features.forEach(function(f) {{
  var gt = (f.geometry || {{}}).type || '';
  if (gt === 'Point' || gt === 'MultiPoint') {{
    pointFeatures.push(f);
  }} else if (gt.indexOf('Line') >= 0) {{
    lineFeatures.push(f);
  }} else {{
    polygonFeatures.push(f);
  }}
}});

var allLayers = [];

// Render Polygon / MultiPolygon
if (polygonFeatures.length > 0) {{
  var polyLayer = L.geoJSON(
    {{type:'FeatureCollection', features: polygonFeatures}},
    {{
      style: sf,
      onEachFeature: function(f, l) {{
        if (f.properties) {{
          l.bindTooltip(mkTooltip(f.properties), {{sticky:true}});
          l.bindPopup(mkTooltip(f.properties));
        }}
        l.on('mouseover', function() {{ l.setStyle({{weight:2.5, fillOpacity:0.95}}); }});
        l.on('mouseout',  function() {{ polyLayer.resetStyle(l); }});
      }}
    }}
  ).addTo(map);
  allLayers.push(polyLayer);
}}

// Render LineString / MultiLineString
if (lineFeatures.length > 0) {{
  var lineLayer = L.geoJSON(
    {{type:'FeatureCollection', features: lineFeatures}},
    {{
      style: sf,
      onEachFeature: function(f, l) {{
        if (f.properties) {{
          l.bindTooltip(mkTooltip(f.properties), {{sticky:true}});
          l.bindPopup(mkTooltip(f.properties));
        }}
      }}
    }}
  ).addTo(map);
  allLayers.push(lineLayer);
}}

// Render Point / MultiPoint — pakai circleMarker
if (pointFeatures.length > 0) {{
  var pointLayer = L.geoJSON(
    {{type:'FeatureCollection', features: pointFeatures}},
    {{
      pointToLayer: function(f, ll) {{
        var s = sf(f);
        return L.circleMarker(ll, {{
          radius: 7,
          fillColor: s.fillColor || '#2e5bff',
          color: '#ffffff',
          weight: 1.5,
          fillOpacity: 0.85
        }});
      }},
      onEachFeature: function(f, l) {{
        if (f.properties) {{
          l.bindTooltip(mkTooltip(f.properties), {{sticky:true}});
          l.bindPopup(mkTooltip(f.properties));
        }}
      }}
    }}
  ).addTo(map);
  allLayers.push(pointLayer);
}}

// Fit bounds ke semua layer
try {{
  var group = L.featureGroup(allLayers);
  var b = group.getBounds();
  if (b.isValid()) map.fitBounds(b, {{padding:[20,20]}});
}} catch(e) {{
  console.warn('fitBounds error:', e);
}}

L.control.layers(
  {{"CartoDB Dark":cartoDark,"CartoDB Light":cartoLight,"OpenStreetMap":osm}},
  {{}},
  {{position:'topright'}}
).addTo(map);
L.control.scale({{imperial:false}}).addTo(map);
</script>
</body></html>"""


class MapToolbar(QFrame):
    colormap_changed = pyqtSignal(str)
    column_changed   = pyqtSignal(str)
    refresh_clicked  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setStyleSheet("QFrame{background:#13151a;border-bottom:1px solid #2d3340;}")
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(8)
        title = QLabel("🗺  PETA")
        title.setStyleSheet("color:#6a7590;font-size:10px;font-weight:bold;letter-spacing:1px;background:transparent;border:none;")
        layout.addWidget(title)
        layout.addStretch()
        lbl = QLabel("Warna:")
        lbl.setStyleSheet("color:#6a7590;font-size:11px;background:transparent;border:none;")
        self.col_combo = QComboBox()
        self.col_combo.setFixedHeight(28)
        self.col_combo.setFixedWidth(150)
        self.col_combo.setStyleSheet("font-size:11px;")
        self.col_combo.currentTextChanged.connect(lambda t: self.column_changed.emit(t))
        cmap_lbl = QLabel("Palet:")
        cmap_lbl.setStyleSheet("color:#6a7590;font-size:11px;background:transparent;border:none;")
        self.cmap_combo = QComboBox()
        self.cmap_combo.setFixedHeight(28)
        self.cmap_combo.setFixedWidth(110)
        self.cmap_combo.addItems([c.title() for c in COLORMAPS[:12]])
        self.cmap_combo.setStyleSheet("font-size:11px;")
        self.cmap_combo.currentTextChanged.connect(lambda t: self.colormap_changed.emit(t.lower()))
        refresh_btn = QPushButton("↻")
        refresh_btn.setObjectName("secondary")
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setToolTip("Refresh peta (Ctrl+R)")
        refresh_btn.clicked.connect(self.refresh_clicked.emit)
        layout.addWidget(lbl)
        layout.addWidget(self.col_combo)
        layout.addWidget(cmap_lbl)
        layout.addWidget(self.cmap_combo)
        layout.addWidget(refresh_btn)

    def set_columns(self, cols: List[str]):
        self.col_combo.blockSignals(True)
        self.col_combo.clear()
        self.col_combo.addItem("(Warna Polos)")
        self.col_combo.addItems(cols)
        self.col_combo.blockSignals(False)

    @property
    def value_col(self):
        t = self.col_combo.currentText()
        return None if t.startswith("(") else t

    @property
    def colormap(self):
        return self.cmap_combo.currentText().lower()


class MapCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_gdf   = None
        self._current_title = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.toolbar = MapToolbar()
        self.toolbar.refresh_clicked.connect(self._refresh)
        self.toolbar.column_changed.connect(lambda _: self._refresh())
        self.toolbar.colormap_changed.connect(lambda _: self._refresh())
        layout.addWidget(self.toolbar)

        if _WEBENGINE_OK:
            self.web_view = QWebEngineView()
            s = self.web_view.settings()
            # Allow CDN resources from inline HTML
            s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            s.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
            self.web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            layout.addWidget(self.web_view, 1)
            self._show_welcome()
        else:
            self._fallback = QLabel("Muat layer untuk melihat peta")
            self._fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._fallback.setStyleSheet("background:#0f1116;color:#6a7590;")
            layout.addWidget(self._fallback, 1)

    def _show_welcome(self):
        html = """<!DOCTYPE html><html>
<head><style>*{margin:0;padding:0;}body{background:#1a1d23;color:#e0e6f0;
font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;}
.box{text-align:center;}.icon{font-size:48px;margin-bottom:14px;}
h2{font-size:20px;margin-bottom:10px;}p{color:#6a7590;font-size:13px;line-height:1.8;}
code{background:#13151a;border:1px solid #2d3340;border-radius:4px;padding:2px 8px;font-size:12px;color:#a0aab8;}
</style></head><body><div class="box">
<div class="icon">🌍</div><h2>Peta Kosong</h2>
<p>Klik dua kali layer di panel kiri,<br>atau gunakan <code>Query Builder</code>
/ <code>Geoprocessing</code><br>untuk menampilkan data spasial di sini.</p>
</div></body></html>"""
        if _WEBENGINE_OK:
            self.web_view.setHtml(html)

    def display(self, gdf, title="", numeric_cols=None):
        self._current_gdf   = gdf
        self._current_title = title
        if numeric_cols is not None:
            self.toolbar.set_columns(numeric_cols)
        self._render(gdf, title)

    def clear(self):
        self._current_gdf = None
        self._show_welcome()
        self.toolbar.set_columns([])

    def _refresh(self):
        if self._current_gdf is not None:
            self._render(self._current_gdf, self._current_title)

    def _render(self, gdf, title):
        if gdf is None or len(gdf) == 0:
            self._show_empty("Tidak ada data untuk ditampilkan")
            return

        # Reproject to WGS84
        try:
            wgs = gdf.copy()
            if wgs.crs is None:
                wgs = wgs.set_crs(4326)
            elif wgs.crs.to_epsg() != 4326:
                wgs = wgs.to_crs(4326)
        except Exception as exc:
            logger.error("Reproject: %s", exc)
            self._show_empty(f"Error proyeksi: {exc}")
            return

        # Limit features
        if len(wgs) > 5000:
            wgs = wgs.head(5000)

        geom_col  = wgs.geometry.name

        # Exclude ALL geometry-type columns from properties
        # (GeoDataFrame bisa punya >1 kolom geom, mis. geom + geom_buffer)
        from shapely.geometry.base import BaseGeometry
        def _is_geom_col(series):
            """Cek apakah series berisi geometri (dtype geometry atau object berisi shapely)."""
            if hasattr(series, 'geom_type'):   # GeoSeries
                return True
            if str(series.dtype) == 'geometry':
                return True
            # Cek sample value
            try:
                sample = series.dropna().iloc[0] if len(series.dropna()) > 0 else None
                if sample is not None and isinstance(sample, BaseGeometry):
                    return True
            except Exception:
                pass
            return False

        prop_cols = [c for c in wgs.columns
                     if c != geom_col and not _is_geom_col(wgs[c])]

        bounds = wgs.total_bounds
        center = [(bounds[1]+bounds[3])/2, (bounds[0]+bounds[2])/2]
        if any(np.isnan(c) for c in center):
            center = [-2.5, 118.0]

        # ── Normalisasi geometri → MultiGeometry 2D ─────────────────────────
        # Standar: semua geometri dikonversi ke tipe Multi yang seragam:
        #   Polygon Z / Polygon       → MultiPolygon 2D
        #   MultiPolygon Z            → MultiPolygon 2D  (strip Z)
        #   LineString / MultiLine    → MultiLineString 2D
        #   Point / MultiPoint        → MultiPoint 2D
        #   GeometryCollection        → per anggota, dikonversi sesuai tipe
        # Ini memastikan layer campuran Polygon+MultiPolygon tetap konsisten.
        from shapely.ops import transform as shp_transform
        from shapely.geometry import (
            Polygon, MultiPolygon, LineString, MultiLineString,
            Point, MultiPoint, GeometryCollection
        )

        def _strip_z(geom):
            """Hapus koordinat Z, kembalikan geometri 2D."""
            if geom is None or geom.is_empty:
                return geom
            if geom.has_z:
                return shp_transform(lambda x, y, z=None: (x, y), geom)
            return geom

        def _to_multi(geom):
            """
            Konversi ke tipe Multi yang sesuai, strip Z, 1 feature per baris.
            Polygon        → MultiPolygon
            MultiPolygon   → MultiPolygon  (tetap, hanya strip Z)
            LineString     → MultiLineString
            MultiLineString→ MultiLineString
            Point          → MultiPoint
            MultiPoint     → MultiPoint
            GeometryCollection → konversi per anggota
            """
            if geom is None or geom.is_empty:
                return None
            geom = _strip_z(geom)
            if isinstance(geom, Polygon):
                return MultiPolygon([geom])
            if isinstance(geom, MultiPolygon):
                return geom
            if isinstance(geom, LineString):
                return MultiLineString([geom])
            if isinstance(geom, MultiLineString):
                return geom
            if isinstance(geom, Point):
                return MultiPoint([geom])
            if isinstance(geom, MultiPoint):
                return geom
            if isinstance(geom, GeometryCollection):
                # Ambil anggota terbanyak lalu konversi
                polys = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon))]
                lines = [g for g in geom.geoms if isinstance(g, (LineString, MultiLineString))]
                pts   = [g for g in geom.geoms if isinstance(g, (Point, MultiPoint))]
                if polys:
                    all_polys = []
                    for p in polys:
                        p = _strip_z(p)
                        if isinstance(p, Polygon):
                            all_polys.append(p)
                        else:
                            all_polys.extend(p.geoms)
                    return MultiPolygon(all_polys)
                if lines:
                    all_lines = []
                    for ln in lines:
                        ln = _strip_z(ln)
                        if isinstance(ln, LineString):
                            all_lines.append(ln)
                        else:
                            all_lines.extend(ln.geoms)
                    return MultiLineString(all_lines)
                if pts:
                    all_pts = []
                    for p in pts:
                        p = _strip_z(p)
                        if isinstance(p, Point):
                            all_pts.append(p)
                        else:
                            all_pts.extend(p.geoms)
                    return MultiPoint(all_pts)
            return None

        # Build GeoJSON inline — satu feature per baris, tipe Multi seragam
        features = []
        for idx, row in wgs.iterrows():
            raw_geom = row[geom_col]
            geom     = _to_multi(raw_geom)
            if geom is None or geom.is_empty:
                continue
            try:
                props = {}
                for col in prop_cols[:15]:
                    val = row[col]
                    if hasattr(val, "item"):
                        val = val.item()
                    if isinstance(val, float) and np.isnan(val):
                        val = None
                    elif not isinstance(val, (int, float, bool, str, type(None))):
                        val = str(val)
                    props[col] = val
            except Exception:
                props = {}
            try:
                features.append({
                    "type":       "Feature",
                    "id":         str(idx),
                    "geometry":   geom.__geo_interface__,
                    "properties": props,
                })
            except Exception:
                continue

        geojson_data = {"type":"FeatureCollection","features":features}

        # Choropleth
        value_col     = self.toolbar.value_col
        colormap_name = self.toolbar.colormap
        feature_colors = color_stops = None
        vmin = vmax = 0

        if value_col and value_col in wgs.columns:
            try:
                vals = wgs[value_col].dropna().astype(float)
                vmin, vmax = float(vals.min()), float(vals.max())
                cmap = plt.get_cmap(colormap_name)
                norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
                feature_colors = {}
                for idx, row in wgs.iterrows():
                    try:
                        feature_colors[str(idx)] = mcolors.to_hex(cmap(norm(float(row[value_col]))))
                    except Exception:
                        feature_colors[str(idx)] = "#555555"
                color_stops = [mcolors.to_hex(cmap(i/4)) for i in range(5)]
            except Exception as exc:
                logger.warning("Choropleth: %s", exc)

        geom_types = ", ".join(wgs.geometry.geom_type.dropna().unique())
        html = _build_map_html(
            geojson_data=geojson_data, center=center, title=title,
            feature_colors=feature_colors, color_stops=color_stops,
            vmin=vmin, vmax=vmax, value_col=value_col,
            count=len(features), geom_types=geom_types,
        )

        if _WEBENGINE_OK:
            # Cek apakah Leaflet sudah tersedia lokal
            from core.leaflet_cache import is_available as leaflet_cached
            if leaflet_cached():
                # Leaflet di-embed inline → load via file:// (fully offline)
                import tempfile
                import os
                tmp = tempfile.NamedTemporaryFile(
                    suffix=".html", delete=False, prefix="spaque_map_",
                    mode="w", encoding="utf-8"
                )
                tmp.write(html)
                tmp.close()
                if hasattr(self, "_map_tmp") and self._map_tmp:
                    try:
                        os.unlink(self._map_tmp)
                    except Exception:
                        pass
                self._map_tmp = tmp.name
                self.web_view.load(QUrl.fromLocalFile(tmp.name))
                logger.debug("Map rendered (offline): %d features", len(features))
            else:
                # Leaflet dari CDN → pakai setHtml dengan base_url HTTPS
                # agar QWebEngine izinkan akses ke CDN external
                self.web_view.setHtml(html, QUrl("https://spaque.app/map/"))
                logger.debug("Map rendered (CDN): %d features", len(features))
        else:
            self._render_matplotlib_fallback(wgs, title, value_col, colormap_name)

    def _render_matplotlib_fallback(self, gdf, title, value_col, colormap):
        from PyQt6.QtGui import QPixmap
        try:
            fig, ax = plt.subplots(figsize=(10,7))
            fig.patch.set_facecolor("#1a1d23")
            ax.set_facecolor("#13151a")
            if value_col and value_col in gdf.columns:
                gdf.plot(column=value_col, cmap=colormap, ax=ax, legend=True,
                         edgecolor="#ffffff33", linewidth=0.3)
            else:
                gdf.plot(ax=ax, color="#2e5bff", edgecolor="#ffffff33",
                         linewidth=0.3, alpha=0.8)
            ax.set_title(title, color="#e0e6f0", fontsize=12)
            for spine in ax.spines.values():
                spine.set_edgecolor("#2d3340")
            ax.grid(True, color="#2d3340", linewidth=0.5, alpha=0.4)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                fig.savefig(f.name, dpi=110, bbox_inches="tight", facecolor="#1a1d23")
                plt.close(fig)
                pm = QPixmap(f.name)
                self._fallback.setPixmap(pm.scaled(
                    self._fallback.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
        except Exception as exc:
            self._fallback.setText(f"Render gagal: {exc}")

    def _show_empty(self, msg):
        html = f"""<!DOCTYPE html><html><head><style>
body{{background:#1a1d23;color:#6a7590;display:flex;align-items:center;
justify-content:center;height:100vh;font-family:sans-serif;margin:0;font-size:13px;}}
</style></head><body><div>⚠️ {msg}</div></body></html>"""
        if _WEBENGINE_OK:
            self.web_view.setHtml(html)
