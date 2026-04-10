"""
tests/unit/test_importers.py — Unit tests for spatial file import pipeline
"""

import sys
import os
from pathlib import Path

import pytest
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from core.importers.base import (
    ImportSpec, SpatialImporter,
    FORMAT_REGISTRY, SUPPORTED_EXTENSIONS,
    get_file_info, _safe_ident, _auto_detect_col,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_gdf_polygon():
    return gpd.GeoDataFrame(
        {"nama": ["A", "B", "C"], "luas": [10.5, 22.3, 7.8]},
        geometry=[
            Polygon([(0,0),(1,0),(1,1),(0,1)]),
            Polygon([(1,0),(2,0),(2,1),(1,1)]),
            Polygon([(0,1),(1,1),(1,2),(0,2)]),
        ],
        crs="EPSG:4326",
    )


@pytest.fixture
def sample_gdf_point():
    return gpd.GeoDataFrame(
        {"nama": ["P1", "P2"], "nilai": [100, 200]},
        geometry=[Point(110.3, -7.8), Point(110.5, -7.9)],
        crs="EPSG:4326",
    )


@pytest.fixture
def geojson_file(sample_gdf_polygon, tmp_path):
    p = tmp_path / "test_layer.geojson"
    sample_gdf_polygon.to_file(str(p), driver="GeoJSON")
    return p


@pytest.fixture
def shapefile(sample_gdf_polygon, tmp_path):
    p = tmp_path / "test_layer.shp"
    sample_gdf_polygon.to_file(str(p), driver="ESRI Shapefile")
    return p


@pytest.fixture
def gpkg_file(sample_gdf_polygon, tmp_path):
    p = tmp_path / "test_layer.gpkg"
    sample_gdf_polygon.to_file(str(p), driver="GPKG")
    return p


@pytest.fixture
def csv_file(tmp_path):
    df = pd.DataFrame({
        "nama": ["Titik A", "Titik B", "Titik C"],
        "longitude": [110.3665, 110.4200, 110.2500],
        "latitude":  [-7.7956, -7.8100, -7.7500],
        "elevasi":   [45.2, 120.5, 30.0],
    })
    p = tmp_path / "titik_sample.csv"
    df.to_csv(str(p), index=False)
    return p


@pytest.fixture
def csv_file_semicolon(tmp_path):
    p = tmp_path / "titik_semicolon.csv"
    p.write_text(
        "nama;lon;lat\n"
        "A;110.3;-7.8\n"
        "B;110.4;-7.9\n"
    )
    return p


# ── _safe_ident tests ─────────────────────────────────────────────────────────

class TestSafeIdent:
    def test_lowercase(self):
        assert _safe_ident("KAWASAN") == "kawasan"

    def test_spaces_to_underscore(self):
        assert _safe_ident("kawasan hutan") == "kawasan_hutan"

    def test_special_chars_removed(self):
        assert _safe_ident("batas-desa!") == "batas_desa"

    def test_leading_digit_prefixed(self):
        assert _safe_ident("1layer").startswith("t_")

    def test_multiple_underscores_collapsed(self):
        assert "__" not in _safe_ident("batas  desa!!kawasan")

    def test_max_length(self):
        long = "a" * 100
        assert len(_safe_ident(long)) <= 63

    def test_empty_string_fallback(self):
        result = _safe_ident("!!!###")
        assert result == "layer"

    def test_unicode_name(self):
        result = _safe_ident("batas_desa_2024")
        assert result == "batas_desa_2024"


# ── _auto_detect_col tests ────────────────────────────────────────────────────

class TestAutoDetectCol:
    def test_detect_longitude(self):
        cols = ["nama", "longitude", "latitude", "elevasi"]
        assert _auto_detect_col(cols, ["lon", "long", "longitude", "x"]) == "longitude"

    def test_detect_lat(self):
        cols = ["nama", "lat", "lon"]
        assert _auto_detect_col(cols, ["lat", "latitude", "y"]) == "lat"

    def test_case_insensitive(self):
        cols = ["Nama", "LON", "LAT"]
        assert _auto_detect_col(cols, ["lon"]) == "LON"

    def test_returns_none_when_not_found(self):
        cols = ["nama", "kode"]
        assert _auto_detect_col(cols, ["lon", "longitude", "x"]) is None

    def test_indonesian_alias(self):
        cols = ["nama", "bujur", "lintang"]
        assert _auto_detect_col(cols, ["lon", "long", "longitude", "x", "bujur"]) == "bujur"


# ── FORMAT_REGISTRY tests ─────────────────────────────────────────────────────

class TestFormatRegistry:
    def test_all_formats_have_extensions(self):
        for fmt in FORMAT_REGISTRY:
            assert fmt.extensions, f"Format {fmt.label} has no extensions"

    def test_shp_in_supported(self):
        assert ".shp" in SUPPORTED_EXTENSIONS

    def test_geojson_in_supported(self):
        assert ".geojson" in SUPPORTED_EXTENSIONS
        assert ".json" in SUPPORTED_EXTENSIONS

    def test_gpkg_in_supported(self):
        assert ".gpkg" in SUPPORTED_EXTENSIONS

    def test_csv_is_csv_like(self):
        fmt = SUPPORTED_EXTENSIONS[".csv"]
        assert fmt.is_csv_like is True

    def test_shp_not_csv_like(self):
        fmt = SUPPORTED_EXTENSIONS[".shp"]
        assert fmt.is_csv_like is False

    def test_12_formats(self):
        assert len(FORMAT_REGISTRY) == 12


# ── get_file_info tests ───────────────────────────────────────────────────────

class TestGetFileInfo:
    def test_geojson_info(self, geojson_file):
        info = get_file_info(geojson_file)
        assert info["format"] == "GeoJSON"
        assert info["supported"] is True
        assert info["is_csv"] is False
        assert info["size_mb"] > 0

    def test_csv_info(self, csv_file):
        info = get_file_info(csv_file)
        assert info["is_csv"] is True
        assert info["supported"] is True

    def test_unsupported_ext(self, tmp_path):
        f = tmp_path / "data.xyz"
        f.write_text("hello")
        info = get_file_info(f)
        assert info["supported"] is False


# ── ImportSpec tests ──────────────────────────────────────────────────────────

class TestImportSpec:
    def test_resolved_table_from_filename(self):
        spec = ImportSpec(file_path=Path("/data/kawasan hutan.shp"))
        assert spec.resolved_table == "kawasan_hutan"

    def test_resolved_table_explicit(self):
        spec = ImportSpec(
            file_path=Path("/data/layer.shp"),
            target_table="my_table",
        )
        assert spec.resolved_table == "my_table"

    def test_format_from_extension(self):
        spec = ImportSpec(file_path=Path("/data/layer.geojson"))
        assert spec.format == "geojson"

    def test_defaults(self):
        spec = ImportSpec(file_path=Path("/data/layer.gpkg"))
        assert spec.target_schema == "public"
        assert spec.if_exists == "fail"
        assert spec.geom_col_name == "geom"


# ── SpatialImporter (file reading only, no DB) ────────────────────────────────

class TestSpatialImporterReading:
    """Tests that only exercise file reading, not PostGIS writing."""

    def _make_importer(self):
        """Importer with a None DB (only use _read_file)."""
        imp = SpatialImporter(None)
        return imp

    def test_read_geojson(self, geojson_file):
        imp = self._make_importer()
        spec = ImportSpec(file_path=geojson_file)
        gdf = imp._read_file(spec)
        assert gdf is not None
        assert len(gdf) == 3
        assert "nama" in gdf.columns

    def test_read_shapefile(self, shapefile):
        imp = self._make_importer()
        spec = ImportSpec(file_path=shapefile)
        gdf = imp._read_file(spec)
        assert gdf is not None
        assert len(gdf) == 3

    def test_read_gpkg(self, gpkg_file):
        imp = self._make_importer()
        spec = ImportSpec(file_path=gpkg_file)
        gdf = imp._read_file(spec)
        assert gdf is not None
        assert len(gdf) == 3

    def test_read_csv_auto_detect(self, csv_file):
        imp = self._make_importer()
        spec = ImportSpec(file_path=csv_file, source_srid=4326)
        gdf = imp._read_csv(spec)
        assert gdf is not None
        assert len(gdf) == 3
        assert gdf.geometry.geom_type.unique()[0] == "Point"

    def test_read_csv_manual_cols(self, csv_file_semicolon):
        imp = self._make_importer()
        spec = ImportSpec(
            file_path=csv_file_semicolon,
            lon_col="lon",
            lat_col="lat",
            csv_delimiter=";",
        )
        gdf = imp._read_csv(spec)
        assert len(gdf) == 2
        assert gdf.crs.to_epsg() == 4326

    def test_read_csv_missing_cols_raises(self, tmp_path):
        p = tmp_path / "bad.csv"
        p.write_text("name,value\nA,1\nB,2\n")
        imp = self._make_importer()
        spec = ImportSpec(file_path=p)
        with pytest.raises(ValueError, match="Kolom koordinat tidak ditemukan"):
            imp._read_csv(spec)

    def test_fix_geometry_drops_null(self, sample_gdf_polygon):
        imp = self._make_importer()
        # Add a null geometry row
        import pandas as pd
        null_row = gpd.GeoDataFrame(
            {"nama": ["NULL"], "luas": [0.0]},
            geometry=[None],
            crs="EPSG:4326",
        )
        gdf_with_null = pd.concat([sample_gdf_polygon, null_row], ignore_index=True)
        fixed, warnings = imp._fix_geometry(gdf_with_null)
        assert len(fixed) == 3  # null row removed
        assert any("null" in w.lower() for w in warnings)

    def test_fix_geometry_no_warnings_for_clean(self, sample_gdf_polygon):
        imp = self._make_importer()
        fixed, warnings = imp._fix_geometry(sample_gdf_polygon)
        assert len(fixed) == 3
        assert warnings == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
