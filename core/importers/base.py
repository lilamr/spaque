"""
core/importers/base.py
Spatial file import pipeline: read file → validate → push to PostGIS.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

import geopandas as gpd
import pandas as pd
from pyproj import CRS

from utils.logger import get_logger

logger = get_logger("spaque.importers")


# ── Import spec (options chosen by user in dialog) ────────────────────────────

@dataclass
class ImportSpec:
    """Everything the user configured in the Import dialog."""
    file_path: Path
    target_schema: str = "public"
    target_table: str = ""           # auto-derived from filename if empty
    target_srid: int = 4326
    if_exists: str = "fail"          # "fail" | "replace" | "append"
    # CSV-specific
    lon_col: str = ""
    lat_col: str = ""
    csv_delimiter: str = ","
    csv_encoding: str = "utf-8"
    # Reprojection
    source_srid: Optional[int] = None   # override auto-detected CRS
    reproject_to: Optional[int] = None  # reproject before import
    # Column options
    drop_cols: List[str] = field(default_factory=list)
    # Geometry column name in PostGIS
    geom_col_name: str = "geom"

    @property
    def resolved_table(self) -> str:
        if self.target_table:
            return _safe_ident(self.target_table)
        return _safe_ident(self.file_path.stem)

    @property
    def format(self) -> str:
        return self.file_path.suffix.lower().lstrip(".")


@dataclass
class ImportResult:
    success: bool
    message: str
    rows_imported: int = 0
    schema: str = ""
    table: str = ""
    geom_type: str = ""
    srid: int = 0
    columns: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


# ── Format registry ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FormatInfo:
    label: str
    extensions: Tuple[str, ...]
    driver: Optional[str]          # fiona driver name, None = special handling
    icon: str
    supports_crs: bool = True      # False for CSV (CRS must be set manually)
    is_csv_like: bool = False


FORMAT_REGISTRY: List[FormatInfo] = [
    FormatInfo("ESRI Shapefile",    (".shp",),               "ESRI Shapefile", "🗂"),
    FormatInfo("GeoJSON",           (".geojson", ".json"),    "GeoJSON",        "📋"),
    FormatInfo("GeoPackage",        (".gpkg",),               "GPKG",           "📦"),
    FormatInfo("KML / KMZ",         (".kml", ".kmz"),         "KML",            "📍"),
    FormatInfo("MapInfo TAB",       (".tab",),                "MapInfo File",   "🗺"),
    FormatInfo("MapInfo MIF",       (".mif",),                "MapInfo File",   "🗺"),
    FormatInfo("GML",               (".gml",),                "GML",            "📄"),
    FormatInfo("GPX",               (".gpx",),                "GPX",            "🧭"),
    FormatInfo("FlatGeobuf",        (".fgb",),                "FlatGeobuf",     "⚡"),
    FormatInfo("DXF (AutoCAD)",     (".dxf",),                "DXF",            "📐"),
    FormatInfo("OpenFileGDB",       (".gdb",),                "OpenFileGDB",    "🗄"),
    FormatInfo("CSV + Koordinat",   (".csv", ".txt", ".tsv"), None,             "📊",
               supports_crs=False, is_csv_like=True),
]

SUPPORTED_EXTENSIONS: Dict[str, FormatInfo] = {
    ext: fmt
    for fmt in FORMAT_REGISTRY
    for ext in fmt.extensions
}

FILE_FILTER = "Semua Format Spasial ({});;{};;Semua File (*.*)".format(
    " ".join(f"*{ext}" for fmt in FORMAT_REGISTRY for ext in fmt.extensions),
    ";;".join(
        "{} ({})".format(fmt.label, " ".join(f"*{e}" for e in fmt.extensions))
        for fmt in FORMAT_REGISTRY
    ),
)


# ── Importer engine ───────────────────────────────────────────────────────────

class SpatialImporter:
    """
    Reads any supported spatial file into a GeoDataFrame,
    then writes it into PostGIS using to_postgis().
    """

    def __init__(self, db_connection):
        self._conn = db_connection   # DatabaseConnection instance

    # ── Public API ────────────────────────────────────────────────────────────

    def preview(self, spec: ImportSpec) -> Tuple[Optional[gpd.GeoDataFrame], str]:
        """
        Read file and return (gdf_sample_10rows, info_message).
        Does NOT write to database. Used for the preview panel.
        """
        try:
            gdf = self._read_file(spec)
            if gdf is None or len(gdf) == 0:
                return None, "File kosong atau tidak bisa dibaca"

            info = (
                f"{len(gdf):,} fitur  ·  "
                f"{gdf.geometry.geom_type.unique()[0]}  ·  "
                f"CRS: {gdf.crs.to_string() if gdf.crs else 'Tidak diketahui'}  ·  "
                f"{len(gdf.columns)} kolom"
            )
            return gdf.head(10), info
        except Exception as exc:
            logger.error("Preview failed: %s", exc)
            return None, f"Error membaca file: {exc}"

    def run(self, spec: ImportSpec) -> ImportResult:
        """Full import: read → validate → reproject → write to PostGIS."""
        table = spec.resolved_table
        warnings: List[str] = []

        # 1. Read file
        try:
            gdf = self._read_file(spec)
        except Exception as exc:
            return ImportResult(False, f"Gagal membaca file: {exc}")

        if gdf is None or len(gdf) == 0:
            return ImportResult(False, "File tidak mengandung data atau geometri")

        # 2. Validate geometry
        gdf, geom_warn = self._fix_geometry(gdf)
        warnings.extend(geom_warn)

        # 3. Apply source CRS override
        if spec.source_srid and (gdf.crs is None):
            try:
                gdf = gdf.set_crs(spec.source_srid)
                logger.info("Applied source CRS: EPSG:%d", spec.source_srid)
            except Exception as exc:
                warnings.append(f"Tidak bisa set CRS: {exc}")

        # 4. Reproject if requested
        if spec.reproject_to and gdf.crs:
            try:
                gdf = gdf.to_crs(spec.reproject_to)
                logger.info("Reprojected to EPSG:%d", spec.reproject_to)
            except Exception as exc:
                warnings.append(f"Reproject gagal: {exc}")

        # 5. Set target SRID from CRS or fallback
        srid = spec.target_srid
        if gdf.crs:
            epsg = gdf.crs.to_epsg()
            if epsg:
                srid = epsg

        # 6. Drop requested columns
        if spec.drop_cols:
            cols_to_drop = [c for c in spec.drop_cols if c in gdf.columns]
            gdf = gdf.drop(columns=cols_to_drop)

        # 7. Rename geometry column
        if gdf.geometry.name != spec.geom_col_name:
            gdf = gdf.rename_geometry(spec.geom_col_name)

        # 8. Sanitize column names (PostgreSQL safe)
        gdf.columns = [_safe_ident(c) if c != spec.geom_col_name else c
                       for c in gdf.columns]

        # 9. Write to PostGIS
        try:
            engine = self._conn.sqlalchemy_engine()
            row_count = len(gdf)

            gdf.to_postgis(
                name=table,
                con=engine,
                schema=spec.target_schema,
                if_exists=spec.if_exists,
                index=False,
                chunksize=500,
            )

            geom_type = gdf.geometry.geom_type.unique()[0]
            cols = list(gdf.columns)

            logger.info(
                "Import OK: %d rows → %s.%s (EPSG:%d, %s)",
                row_count, spec.target_schema, table, srid, geom_type
            )
            return ImportResult(
                success=True,
                message=(f"Berhasil import {row_count:,} fitur ke "
                         f'"{spec.target_schema}"."{table}"'),
                rows_imported=row_count,
                schema=spec.target_schema,
                table=table,
                geom_type=geom_type,
                srid=srid,
                columns=cols,
                warnings=warnings,
            )

        except Exception as exc:
            logger.error("PostGIS write failed: %s", exc)
            return ImportResult(False, f"Gagal menulis ke PostGIS: {exc}",
                                warnings=warnings)

    # ── File readers ──────────────────────────────────────────────────────────

    def _read_file(self, spec: ImportSpec) -> Optional[gpd.GeoDataFrame]:
        path = spec.file_path
        ext  = path.suffix.lower()
        fmt  = SUPPORTED_EXTENSIONS.get(ext)

        if fmt and fmt.is_csv_like:
            return self._read_csv(spec)

        # GeoDataFrame.read_file handles everything fiona supports
        kwargs: Dict[str, Any] = {}

        # KMZ → need to handle zipped KML
        if ext == ".kmz":
            return self._read_kmz(path)

        # GDB → directory, open with fiona
        if ext == ".gdb":
            import fiona
            layers = fiona.listlayers(str(path))
            if not layers:
                raise ValueError("FileGDB tidak mengandung layer")
            # Import all layers merged, or just first
            gdfs = []
            for lyr in layers:
                g = gpd.read_file(str(path), layer=lyr)
                gdfs.append(g)
            if len(gdfs) == 1:
                return gdfs[0]
            return pd.concat(gdfs, ignore_index=True)

        # Everything else
        return gpd.read_file(str(path), **kwargs)

    def _read_csv(self, spec: ImportSpec) -> Optional[gpd.GeoDataFrame]:
        """Read CSV/TXT with lat/lon columns into GeoDataFrame."""
        df = pd.read_csv(
            str(spec.file_path),
            sep=spec.csv_delimiter,
            encoding=spec.csv_encoding,
            low_memory=False,
        )

        if not spec.lon_col or not spec.lat_col:
            # Try to auto-detect
            lon_col = _auto_detect_col(df.columns, ["lon","long","longitude","x","bujur"])
            lat_col = _auto_detect_col(df.columns, ["lat","latitude","y","lintang"])
            if not lon_col or not lat_col:
                raise ValueError(
                    "Kolom koordinat tidak ditemukan. "
                    "Tentukan kolom Longitude dan Latitude secara manual."
                )
        else:
            lon_col = spec.lon_col
            lat_col = spec.lat_col

        # Convert to numeric
        df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
        df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
        df = df.dropna(subset=[lon_col, lat_col])

        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs=spec.source_srid or 4326,
        )
        return gdf

    def _read_kmz(self, path: Path) -> gpd.GeoDataFrame:
        """Unzip KMZ and read the inner KML."""
        import zipfile, tempfile
        with zipfile.ZipFile(str(path)) as zf:
            kml_files = [n for n in zf.namelist() if n.endswith(".kml")]
            if not kml_files:
                raise ValueError("Tidak ada file KML di dalam KMZ")
            with tempfile.TemporaryDirectory() as tmp:
                zf.extractall(tmp)
                return gpd.read_file(str(Path(tmp) / kml_files[0]))

    # ── Geometry repair ───────────────────────────────────────────────────────

    def _fix_geometry(self, gdf: gpd.GeoDataFrame) -> Tuple[gpd.GeoDataFrame, List[str]]:
        """Remove null/invalid geometries, optionally buffer(0) to fix invalids."""
        warnings: List[str] = []
        original = len(gdf)

        # Drop null geometry
        gdf = gdf[~gdf.geometry.isna()].copy()
        dropped_null = original - len(gdf)
        if dropped_null:
            warnings.append(f"{dropped_null} fitur dengan geometri null dihapus")

        # Fix invalid geometries with buffer(0) trick
        invalid_mask = ~gdf.geometry.is_valid
        invalid_count = invalid_mask.sum()
        if invalid_count:
            gdf.loc[invalid_mask, gdf.geometry.name] = (
                gdf.loc[invalid_mask, gdf.geometry.name].buffer(0)
            )
            warnings.append(f"{invalid_count} geometri tidak valid diperbaiki (buffer 0)")

        return gdf, warnings


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_ident(name: str, max_len: int = 63) -> str:
    """Convert string to a safe PostgreSQL identifier."""
    name = str(name).strip().lower()
    name = re.sub(r"[^\w]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if name and name[0].isdigit():
        name = "t_" + name
    return name[:max_len] or "layer"


def _auto_detect_col(columns, candidates: List[str]) -> Optional[str]:
    """Case-insensitive column name matching from a candidate list."""
    col_lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand in col_lower:
            return col_lower[cand]
    return None


def get_file_info(path: Path) -> Dict[str, Any]:
    """Quick file metadata without full read."""
    fmt = SUPPORTED_EXTENSIONS.get(path.suffix.lower())
    size_mb = path.stat().st_size / 1_048_576 if path.exists() else 0
    return {
        "name": path.name,
        "format": fmt.label if fmt else "Unknown",
        "icon": fmt.icon if fmt else "📁",
        "size_mb": size_mb,
        "is_csv": fmt.is_csv_like if fmt else False,
        "supported": fmt is not None,
    }
