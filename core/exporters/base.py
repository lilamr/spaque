"""
core/exporters/base.py — Abstract exporter
core/exporters/shapefile.py
core/exporters/geojson.py
(Combined in one file; import individually in production)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple

import geopandas as gpd

from utils.logger import get_logger

logger = get_logger("spaque.exporters")


# ── Base ──────────────────────────────────────────────────────────────────────

class BaseExporter(ABC):
    name: str = ""
    extension: str = ""
    file_filter: str = ""

    @abstractmethod
    def export(self, gdf: gpd.GeoDataFrame, path: Path) -> Tuple[bool, str]:
        """Export GeoDataFrame to file. Returns (success, message)."""


# ── GeoJSON ───────────────────────────────────────────────────────────────────

class GeoJSONExporter(BaseExporter):
    name = "GeoJSON"
    extension = ".geojson"
    file_filter = "GeoJSON Files (*.geojson)"

    def export(self, gdf: gpd.GeoDataFrame, path: Path) -> Tuple[bool, str]:
        try:
            out = gdf.copy()
            if out.crs is None:
                out = out.set_crs(4326)
            elif out.crs.to_epsg() != 4326:
                out = out.to_crs(4326)
            out.to_file(str(path), driver="GeoJSON")
            count = len(out)
            msg = f"Berhasil export {count:,} fitur ke {path.name}"
            logger.info(msg)
            return True, msg
        except Exception as exc:
            logger.error("GeoJSON export failed: %s", exc)
            return False, str(exc)


# ── Shapefile ─────────────────────────────────────────────────────────────────

class ShapefileExporter(BaseExporter):
    name = "Shapefile"
    extension = ".shp"
    file_filter = "ESRI Shapefile (*.shp)"

    def export(self, gdf: gpd.GeoDataFrame, path: Path) -> Tuple[bool, str]:
        try:
            # Truncate column names to 10 chars (SHP limit)
            out = gdf.copy()
            out.columns = [c[:10] for c in out.columns]
            out.to_file(str(path), driver="ESRI Shapefile")
            count = len(out)
            msg = f"Berhasil export {count:,} fitur ke {path.name}"
            logger.info(msg)
            return True, msg
        except Exception as exc:
            logger.error("Shapefile export failed: %s", exc)
            return False, str(exc)


# ── CSV (attributes only) ─────────────────────────────────────────────────────

class CSVExporter(BaseExporter):
    name = "CSV"
    extension = ".csv"
    file_filter = "CSV Files (*.csv)"

    def export(self, gdf: gpd.GeoDataFrame, path: Path) -> Tuple[bool, str]:
        try:
            df = gdf.drop(columns=[gdf.geometry.name], errors="ignore")
            df.to_csv(str(path), index=False)
            msg = f"Berhasil export {len(df):,} baris ke {path.name}"
            logger.info(msg)
            return True, msg
        except Exception as exc:
            logger.error("CSV export failed: %s", exc)
            return False, str(exc)


# ── Registry ──────────────────────────────────────────────────────────────────

EXPORTERS: dict[str, BaseExporter] = {
    e.name: e
    for e in [GeoJSONExporter(), ShapefileExporter(), CSVExporter()]
}
