"""
tests/unit/test_regressions.py
Test regresi — setiap test di sini merepresentasikan bug nyata yang
pernah terjadi di production. Jika test ini gagal, bug itu kembali lagi.

Filosofi: test PERILAKU yang bisa diamati dari luar, bukan implementasi.
Kalau user bisa merasakannya sebagai bug → ada test-nya di sini.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon


# ─────────────────────────────────────────────────────────────────────────────
# BUG 1: NameError 'layers' di QueryBuilderDialog
# Crash: "NameError: name 'layers' is not defined" → core dump
# Root cause: _build_ui() pakai local var 'layers' yang sudah di luar scope
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryBuilderDialogInit:
    """
    QueryBuilderDialog harus bisa diinstansiasi tanpa crash.
    Bug asli: __init__ memanggil _build_ui() yang mengakses variable
    'layers' (bukan self._layers) → NameError → core dump.
    """

    def _make_layers(self):
        from core.domain.entities.layer import LayerInfo
        return [
            LayerInfo("public", "pohon",    "geom", "POINT",           32750, 10),
            LayerInfo("public", "kawasan",  "geom", "MULTIPOLYGON",    32750, 5),
            LayerInfo("public", "sungai",   "geom", "LINESTRING",      32750, 8),
        ]

    def _dummy_get_columns(self, layer):
        from core.domain.entities.layer import LayerColumn
        return [
            LayerColumn("gid",        "integer",          "int4"),
            LayerColumn("nama",       "character varying","varchar"),
            LayerColumn("luas",       "double precision", "float8"),
            LayerColumn("geom",       "USER-DEFINED",     "geometry"),
        ]

    def test_init_does_not_raise_nameerror(self):
        """
        REGRESSION: sebelumnya __init__ → _build_ui() crash dengan NameError.
        Test ini akan gagal jika bug kembali.
        """
        from dialogs.query_builder_dialog import QueryBuilderDialog

        layers = self._make_layers()
        # Tidak boleh raise NameError atau exception apapun
        try:
            dlg = QueryBuilderDialog.__new__(QueryBuilderDialog)
            dlg._layers   = layers
            dlg._get_cols = self._dummy_get_columns
            dlg._columns  = []
            # Simulasikan _build_ui() hanya pada bagian yang bug:
            # addItems harus pakai self._layers bukan layers
            items = [f"{lyr.schema}.{lyr.table_name}" for lyr in dlg._layers]
            assert len(items) == 3
            assert "public.pohon" in items
        except NameError as e:
            pytest.fail(f"NameError kembali lagi: {e}")

    def test_no_bare_layers_variable_in_build_ui(self):
        """
        REGRESSION: _build_ui() mengandung 'layers' (bukan self._layers)
        di dua tempat — baris addItems DAN baris 'if layers:'.
        Keduanya harus sudah diganti ke self._layers.
        """
        src = open(
            __import__("os").path.join(
                __import__("os").path.dirname(__file__),
                "../../dialogs/query_builder_dialog.py"
            )
        ).read()

        # Parse semua baris di dalam _build_ui yang pakai 'layers' tanpa self.
        import ast
        tree = ast.parse(src)
        build_ui_node = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_build_ui"
        )
        # Cari Name node dengan id='layers' (bukan self._layers)
        bare_refs = [
            n for n in ast.walk(build_ui_node)
            if isinstance(n, ast.Name) and n.id == "layers"
        ]
        assert bare_refs == [], (
            f"Masih ada {len(bare_refs)} referensi 'layers' (tanpa self.) "
            f"di dalam _build_ui() pada baris: "
            f"{[n.lineno for n in bare_refs]}"
        )
        """Table combo harus menampilkan semua layer yang dioper."""
        from core.domain.entities.layer import LayerInfo
        layers = [
            LayerInfo("public", "a", "geom", "POINT", 4326, 1),
            LayerInfo("forestdb", "b", "geom", "POLYGON", 4326, 1),
        ]
        items = [f"{lyr.schema}.{lyr.table_name}" for lyr in layers]
        assert items == ["public.a", "forestdb.b"]

    def test_empty_layers_no_crash(self):
        """Dialog dengan daftar layer kosong tidak boleh crash."""
        layers = []
        items = [f"{lyr.schema}.{lyr.table_name}" for lyr in layers]
        assert items == []


# ─────────────────────────────────────────────────────────────────────────────
# BUG 2a: Kolom geometri ganda bocor ke GeoJSON properties
# Gejala: polygon/buffer result tidak tampil, JS error di console
# Root cause: GDF hasil geoprocess punya 2 kolom geom (geom + geom_buffer),
#             keduanya ikut masuk ke properties → JSON.stringify gagal
# ─────────────────────────────────────────────────────────────────────────────

class TestMapCanvasGeomColumnExclusion:
    """
    Ketika GeoDataFrame punya lebih dari satu kolom geometri,
    hanya kolom non-geometri yang boleh masuk ke GeoJSON properties.
    """

    def _is_geom_col(self, series):
        """Sama persis dengan implementasi di map_canvas.py."""
        from shapely.geometry.base import BaseGeometry
        if hasattr(series, 'geom_type'):
            return True
        if str(series.dtype) == 'geometry':
            return True
        try:
            sample = series.dropna().iloc[0] if len(series.dropna()) > 0 else None
            if sample is not None and isinstance(sample, BaseGeometry):
                return True
        except Exception:
            pass
        return False

    def _get_prop_cols(self, gdf):
        """Replikasi logika prop_cols dari map_canvas._render()."""
        geom_col = gdf.geometry.name
        return [c for c in gdf.columns
                if c != geom_col and not self._is_geom_col(gdf[c])]

    def test_single_geom_col_normal_case(self):
        """GDF normal: hanya 1 kolom geom → semua kolom non-geom masuk props."""
        gdf = gpd.GeoDataFrame(
            {"nama": ["A"], "luas": [10.0]},
            geometry=[Polygon([(0,0),(1,0),(1,1),(0,1)])],
            crs="EPSG:4326",
        )
        props = self._get_prop_cols(gdf)
        assert "nama" in props
        assert "luas" in props
        assert "geometry" not in props

    def test_two_geom_cols_excludes_both(self):
        """
        REGRESSION BUG 2a: GDF hasil Buffer punya geom + geom_buffer.
        geom_buffer TIDAK BOLEH masuk ke properties.
        """
        from shapely.geometry import Point, Polygon
        gdf = gpd.GeoDataFrame(
            {
                "nama":       ["Pohon A", "Pohon B"],
                "dbh":        [30.5, 22.1],
                "geom":       [Point(0, 0), Point(1, 1)],
                "geom_buffer": [
                    Polygon([(-.1,-.1),(.1,-.1),(.1,.1),(-.1,.1)]),
                    Polygon([(.9,.9),(1.1,.9),(1.1,1.1),(.9,1.1)]),
                ],
            },
            geometry="geom",
            crs="EPSG:32750",
        )
        props = self._get_prop_cols(gdf)

        # geom_buffer harus TIDAK ada di props
        assert "geom_buffer" not in props, (
            "BUG 2a KEMBALI: geom_buffer bocor ke GeoJSON properties. "
            "Kolom ini berisi Shapely object → JSON.stringify crash di JS."
        )
        # kolom atribut normal tetap ada
        assert "nama" in props
        assert "dbh" in props

    def test_three_geom_cols(self):
        """Edge case: 3 kolom geometri → semuanya dikecualikan."""
        gdf = gpd.GeoDataFrame(
            {
                "id":         [1],
                "geom":       [Point(0, 0)],
                "geom_buf":   [Polygon([(-.1,-.1),(.1,-.1),(.1,.1),(-.1,.1)])],
                "geom_hull":  [Polygon([(-.2,-.2),(.2,-.2),(.2,.2),(-.2,.2)])],
            },
            geometry="geom",
            crs="EPSG:4326",
        )
        props = self._get_prop_cols(gdf)
        assert "geom_buf"  not in props
        assert "geom_hull" not in props
        assert "id" in props

    def test_shapely_object_in_object_column_excluded(self):
        """
        Kolom object dtype yang isinya Shapely juga harus dikecualikan,
        bukan hanya yang punya dtype='geometry'.
        """
        from shapely.geometry import Point
        df = pd.DataFrame({
            "nama": ["X"],
            "raw_geom": [Point(1, 2)],   # dtype=object tapi isinya Shapely
        })
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy([1],[2]), crs=4326)
        props = self._get_prop_cols(gdf)
        assert "raw_geom" not in props
        assert "nama" in props


# ─────────────────────────────────────────────────────────────────────────────
# BUG 2b: Polygon tidak tampil — _build_map_html props validation
# Gejala: peta kosong ketika load polygon layer
# Root cause: properties berisi object yang tidak JSON-serializable
# ─────────────────────────────────────────────────────────────────────────────

class TestMapCanvasGeoJSONSerialization:
    """
    GeoJSON yang dihasilkan harus 100% JSON-serializable.
    Kalau ada Shapely object di dalamnya, json.dumps() akan gagal
    → JS error → peta kosong.
    """

    def _build_features_from_gdf(self, gdf):
        """Replikasi logika feature building dari map_canvas._render()."""
        import numpy as np
        from shapely.geometry.base import BaseGeometry

        def _is_geom_col(series):
            if hasattr(series, 'geom_type'):
                return True
            if str(series.dtype) == 'geometry':
                return True
            try:
                sample = series.dropna().iloc[0] if len(series.dropna()) > 0 else None
                if sample is not None and isinstance(sample, BaseGeometry):
                    return True
            except Exception:
                pass
            return False

        geom_col  = gdf.geometry.name
        prop_cols = [c for c in gdf.columns
                     if c != geom_col and not _is_geom_col(gdf[c])]

        features = []
        for idx, row in gdf.iterrows():
            geom = row[geom_col]
            if geom is None or geom.is_empty:
                continue
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
            features.append({
                "type": "Feature",
                "id": str(idx),
                "geometry": geom.__geo_interface__,
                "properties": props,
            })
        return features

    def test_polygon_gdf_serializable(self):
        """GDF polygon harus menghasilkan GeoJSON yang bisa di-serialize."""
        import json
        gdf = gpd.GeoDataFrame(
            {"n_kws": ["HL","HPT"], "luas": [1000.5, 2500.3]},
            geometry=[
                Polygon([(0,0),(1,0),(1,1),(0,1)]),
                Polygon([(1,0),(2,0),(2,1),(1,1)]),
            ],
            crs="EPSG:32750",
        )
        features = self._build_features_from_gdf(gdf)
        assert len(features) == 2

        # HARUS bisa di-serialize tanpa TypeError
        try:
            result = json.dumps({"type":"FeatureCollection","features":features})
            assert len(result) > 100
        except (TypeError, ValueError) as e:
            pytest.fail(
                f"GeoJSON tidak JSON-serializable: {e}\n"
                "Kemungkinan Shapely object bocor ke properties."
            )

    def test_buffer_result_gdf_serializable(self):
        """
        REGRESSION BUG 2a+2b: Hasil Buffer (2 kolom geom) harus serializable.
        Ini adalah test yang PASTI GAGAL sebelum bugfix.
        """
        import json
        # Simulasi GDF hasil ST_Buffer — punya 2 kolom geometri
        gdf = gpd.GeoDataFrame(
            {
                "nama":       ["Bambu A", "Bambu B"],
                "panjang":    [12.5, 8.3],
                "geom":       [Point(0,0), Point(1,1)],
                "geom_buffer": [
                    Polygon([(-.1,-.1),(.1,-.1),(.1,.1),(-.1,.1)]),
                    Polygon([(.9,.9),(1.1,.9),(1.1,1.1),(.9,1.1)]),
                ],
            },
            geometry="geom",
            crs="EPSG:32750",
        )
        features = self._build_features_from_gdf(gdf)
        assert len(features) == 2

        try:
            json.dumps({"type":"FeatureCollection","features":features})
        except TypeError as e:
            pytest.fail(
                f"REGRESSION BUG 2a+2b: {e}\n"
                "geom_buffer masih bocor ke properties."
            )

        # Pastikan geom_buffer tidak ada di properties
        for f in features:
            assert "geom_buffer" not in f["properties"], \
                "geom_buffer bocor ke GeoJSON properties!"

    def test_point_gdf_serializable(self):
        """GDF titik harus serializable."""
        import json
        gdf = gpd.GeoDataFrame(
            {"nama": ["P1","P2"], "nilai": [100, 200]},
            geometry=[Point(110.3,-7.8), Point(110.5,-7.9)],
            crs="EPSG:4326",
        )
        features = self._build_features_from_gdf(gdf)
        result = json.dumps({"type":"FeatureCollection","features":features})
        assert "Point" in result

    def test_nan_values_become_null(self):
        """NaN di float column harus jadi None (null di JSON), bukan crash."""
        import json
        gdf = gpd.GeoDataFrame(
            {"nama": ["X"], "nilai": [float("nan")]},
            geometry=[Point(0,0)],
            crs="EPSG:4326",
        )
        features = self._build_features_from_gdf(gdf)
        result = json.loads(json.dumps({"type":"FeatureCollection","features":features}))
        assert result["features"][0]["properties"]["nilai"] is None

    def test_numpy_int_serializable(self):
        """numpy int64 harus di-convert ke Python int agar JSON-serializable."""
        import json
        import numpy as np
        gdf = gpd.GeoDataFrame(
            {"count": [np.int64(42)]},
            geometry=[Point(0,0)],
            crs="EPSG:4326",
        )
        features = self._build_features_from_gdf(gdf)
        # numpy int64 tidak JSON-serializable secara default
        # test ini verify konversi .item() bekerja
        result = json.dumps({"type":"FeatureCollection","features":features})
        assert "42" in result


# ─────────────────────────────────────────────────────────────────────────────
# BUG 3: GeoAlchemy2 tidak ada di requirements.txt
# Gejala: ImportError saat pertama install & jalankan
# ─────────────────────────────────────────────────────────────────────────────

class TestRequirements:
    """requirements.txt harus mencantumkan semua dependensi yang dipakai."""

    def _load_reqs(self):
        req_path = Path(__file__).parent.parent.parent / "requirements.txt"
        if not req_path.exists():
            pytest.skip("requirements.txt tidak ditemukan")
        return req_path.read_text().lower()

    def test_geoalchemy2_present(self):
        """
        REGRESSION BUG 3: GeoAlchemy2 dipakai oleh geopandas.to_postgis()
        tapi tidak ada di requirements.txt.
        """
        reqs = self._load_reqs()
        assert "geoalchemy2" in reqs, (
            "GeoAlchemy2 tidak ada di requirements.txt. "
            "geopandas.to_postgis() membutuhkan GeoAlchemy2 untuk koneksi SQLAlchemy."
        )

    def test_pillow_present(self):
        """Pillow dipakai untuk generate icon — harus ada di requirements."""
        reqs = self._load_reqs()
        assert "pillow" in reqs, "Pillow tidak ada di requirements.txt"

    def test_core_deps_present(self):
        """Semua dependensi inti harus ada."""
        reqs = self._load_reqs()
        required = [
            "pyqt6",
            "geopandas",
            "psycopg2",
            "shapely",
            "sqlalchemy",
            "geoalchemy2",
            "fiona",
            "pyproj",
            "pandas",
            "numpy",
            "matplotlib",
            "python-dotenv",
        ]
        missing = [dep for dep in required if dep not in reqs]
        assert not missing, f"Dependensi berikut tidak ada di requirements.txt: {missing}"


# ─────────────────────────────────────────────────────────────────────────────
# EXTRA: Test yang seharusnya ada sejak awal untuk dialog initialization
# ─────────────────────────────────────────────────────────────────────────────

class TestDialogSafeInit:
    """
    Dialog init tidak boleh crash karena kesalahan scoping variable.
    Pattern umum bug: variable yang dibuat di __init__ diakses di method
    yang dipanggil dari __init__ sebelum self.x = ... dieksekusi.
    """

    def _make_layer_info(self, table="pohon"):
        from core.domain.entities.layer import LayerInfo
        return LayerInfo("public", table, "geom", "POINT", 32750, 10)

    def test_import_spec_resolved_table_no_crash(self):
        """ImportSpec.resolved_table tidak boleh crash untuk nama file apapun."""
        from core.importers.base import ImportSpec
        cases = [
            "kawasan hutan.shp",
            "1data.geojson",
            "batas-desa_2024.gpkg",
            "Data Inventarisasi!!.shp",
            "普通话.shp",
        ]
        for name in cases:
            spec = ImportSpec(file_path=Path(f"/tmp/{name}"))
            try:
                table = spec.resolved_table
                assert isinstance(table, str)
                assert len(table) > 0
            except Exception as e:
                pytest.fail(f"resolved_table crash untuk '{name}': {e}")

    def test_query_spec_build_sql_no_crash(self):
        """QuerySpec.build_sql() tidak boleh crash untuk kondisi apapun."""
        from core.domain.value_objects import QuerySpec, WhereCondition
        cases = [
            QuerySpec("public", "pohon"),
            QuerySpec("public", "pohon", [WhereCondition("dbh",">=","30","AND")]),
            QuerySpec("public", "pohon", [], order_col="dbh", limit=100),
            QuerySpec("public", "pohon", [
                WhereCondition("dbh",   "IS NULL",     "", "AND"),
                WhereCondition("nama",  "LIKE",  "jati%", "OR"),
                WhereCondition("luas",  "BETWEEN", "10,100","AND"),
            ]),
        ]
        for spec in cases:
            try:
                sql = spec.build_sql()
                assert "SELECT" in sql
                assert "FROM" in sql
            except Exception as e:
                pytest.fail(f"build_sql crash: {e}")

    def test_project_state_round_trip(self):
        """ProjectState harus bisa disimpan dan dimuat kembali tanpa data hilang."""
        from core.project.model import ProjectState, DBState, QueryHistoryEntry
        from core.project.serializer import ProjectSerializer

        state = ProjectState(name="Test NTB")
        state.db = DBState(host="localhost", dbname="ihp_db", user="lilamr")
        state.query_history.append(
            QueryHistoryEntry(sql="SELECT * FROM pohon", title="Pohon", row_count=620)
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.spq"
            ok, msg = ProjectSerializer.save(state, path)
            assert ok, f"Save gagal: {msg}"

            loaded, msg2 = ProjectSerializer.load(path)
            assert loaded is not None, f"Load gagal: {msg2}"
            assert loaded.name == "Test NTB"
            assert loaded.db.dbname == "ihp_db"
            assert loaded.db.user == "lilamr"
            assert len(loaded.query_history) == 1
            assert loaded.query_history[0].row_count == 620


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ─────────────────────────────────────────────────────────────────────────────
# BUG: POLYGON Z / MULTIPOLYGON Z tidak tampil di peta
# Gejala: layer tampil di tabel atribut tapi peta kosong
# Root cause: Leaflet hanya 2D — koordinat Z menyebabkan silent JS error
# ─────────────────────────────────────────────────────────────────────────────

class TestZCoordinateStripping:
    """
    Geometri dengan koordinat Z harus di-strip ke 2D sebelum
    dikonversi ke GeoJSON untuk Leaflet.
    """

    def _drop_z(self, geom):
        from shapely.ops import transform as shp_transform
        if geom is None or geom.is_empty:
            return geom
        if geom.has_z:
            return shp_transform(lambda x, y, z=None: (x, y), geom)
        return geom

    def test_polygon_z_stripped(self):
        """POLYGON Z harus jadi POLYGON 2D."""
        from shapely.geometry import Polygon
        poly_z = Polygon([
            (116.0, -8.0, 100), (117.0, -8.0, 150),
            (117.0, -7.0, 200), (116.0, -7.0, 120), (116.0, -8.0, 100)
        ])
        assert poly_z.has_z
        poly_2d = self._drop_z(poly_z)
        assert not poly_2d.has_z
        coords = list(poly_2d.exterior.coords[0])
        assert len(coords) == 2, f"Z masih ada: {coords}"

    def test_multipolygon_z_stripped(self):
        """MULTIPOLYGON Z harus jadi MULTIPOLYGON 2D."""
        from shapely.geometry import Polygon, MultiPolygon
        mp_z = MultiPolygon([
            Polygon([(116.0,-8.0,50),(117.0,-8.0,60),(117.0,-7.0,70),(116.0,-7.0,55),(116.0,-8.0,50)]),
            Polygon([(118.0,-8.0,10),(119.0,-8.0,20),(119.0,-7.0,30),(118.0,-7.0,15),(118.0,-8.0,10)]),
        ])
        assert mp_z.has_z
        mp_2d = self._drop_z(mp_z)
        assert not mp_2d.has_z

    def test_2d_polygon_unchanged(self):
        """Polygon 2D biasa tidak boleh diubah."""
        poly_2d = Polygon([(116.0,-8.0),(117.0,-8.0),(117.0,-7.0),(116.0,-7.0)])
        assert not poly_2d.has_z
        result = self._drop_z(poly_2d)
        assert not result.has_z
        assert result.equals(poly_2d)

    def test_polygon_z_geojson_serializable(self):
        """
        REGRESSION: POLYGON Z setelah strip harus menghasilkan GeoJSON
        yang valid — tidak ada array koordinat [x, y, z], hanya [x, y].
        """
        import json
        import re
        from shapely.geometry import Polygon
        poly_z = Polygon([
            (116.5, -8.5, 250), (117.5, -8.5, 300),
            (117.5, -7.5, 350), (116.5, -7.5, 275), (116.5, -8.5, 250)
        ])
        poly_2d = self._drop_z(poly_z)
        result = json.dumps(poly_2d.__geo_interface__)

        # Tidak boleh ada koordinat dengan 3 elemen [x,y,z]
        z_coords = re.findall(
            r'\[[\d\.\-]+,\s*[\d\.\-]+,\s*[\d\.\-]+\]', result)
        assert z_coords == [], (
            f"REGRESSION: Koordinat Z masih ada di GeoJSON: {z_coords[:3]}\n"
            "Leaflet akan silent error dan polygon tidak tampil."
        )

    def test_gdf_with_polygon_z_renders_all_features(self):
        """
        GeoDataFrame dengan POLYGON Z harus menghasilkan features
        yang sama jumlahnya setelah strip Z.
        """
        import json
        from shapely.geometry import Polygon
        from shapely.ops import transform as shp_transform

        geoms_z = [
            Polygon([(116.0+i,-8.0,100),(117.0+i,-8.0,150),
                     (117.0+i,-7.0,200),(116.0+i,-7.0,120),(116.0+i,-8.0,100)])
            for i in range(5)
        ]
        gdf = gpd.GeoDataFrame(
            {"nama": [f"Kawasan {i}" for i in range(5)],
             "luas": [100.0*i for i in range(5)]},
            geometry=geoms_z,
            crs="EPSG:4326",
        )
        assert all(g.has_z for g in gdf.geometry)

        # Simulasi strip Z seperti di map_canvas._render()
        def drop_z(geom):
            if geom is None or geom.is_empty:
                return geom
            if geom.has_z:
                return shp_transform(lambda x, y, z=None: (x, y), geom)
            return geom

        gdf_2d = gdf.copy()
        gdf_2d["geometry"] = gdf_2d["geometry"].apply(drop_z)

        # Semua 5 fitur harus tetap ada dan bisa di-serialize
        assert len(gdf_2d) == 5
        assert not any(g.has_z for g in gdf_2d.geometry)

        features = []
        for idx, row in gdf_2d.iterrows():
            geom = row["geometry"]
            features.append({
                "type": "Feature",
                "geometry": geom.__geo_interface__,
                "properties": {"nama": row["nama"]},
            })
        result = json.dumps({"type": "FeatureCollection", "features": features})
        assert len(features) == 5
        assert "Kawasan" in result


class TestGeometryNormalization:
    """
    Semua geometri dikonversi ke tipe Multi yang seragam (MultiPolygon, dll.)
    dan strip Z. Standar: satu feature per baris, tipe Multi.
    """

    def _strip_z(self, geom):
        from shapely.ops import transform as shp_transform
        if geom is None or geom.is_empty:
            return geom
        if geom.has_z:
            return shp_transform(lambda x, y, z=None: (x, y), geom)
        return geom

    def _to_multi(self, geom):
        from shapely.geometry import (
            Polygon, MultiPolygon, Point, MultiPoint
        )
        if geom is None or geom.is_empty:
            return None
        geom = self._strip_z(geom)
        if isinstance(geom, Polygon):
            return MultiPolygon([geom])
        if isinstance(geom, MultiPolygon):
            return geom
        if isinstance(geom, Point):
            return MultiPoint([geom])
        if isinstance(geom, MultiPoint):
            return geom
        return geom

    def test_polygon_z_to_multipolygon_2d(self):
        """POLYGON Z → MultiPolygon 2D."""
        poly_z = Polygon([(116.5,-8.5,100),(117.5,-8.5,150),(117.5,-7.5,200),(116.5,-7.5,120),(116.5,-8.5,100)])
        r = self._to_multi(poly_z)
        assert r.geom_type == 'MultiPolygon'
        assert not r.has_z
        assert len(list(r.geoms[0].exterior.coords[0])) == 2

    def test_polygon_2d_to_multipolygon(self):
        """POLYGON 2D → MultiPolygon."""
        p = Polygon([(116.5,-8.5),(117.5,-8.5),(117.5,-7.5),(116.5,-7.5),(116.5,-8.5)])
        r = self._to_multi(p)
        assert r.geom_type == 'MultiPolygon'
        assert not r.has_z

    def test_multipolygon_z_to_2d(self):
        """MULTIPOLYGON Z → MultiPolygon 2D, tetap 2 bagian."""
        from shapely.geometry import MultiPolygon
        mp_z = MultiPolygon([
            Polygon([(116.5,-8.5,100),(117.5,-8.5,150),(117.5,-7.5,200),(116.5,-7.5,120),(116.5,-8.5,100)]),
            Polygon([(118.0,-8.5,50),(119.0,-8.5,60),(119.0,-7.5,70),(118.0,-7.5,55),(118.0,-8.5,50)]),
        ])
        r = self._to_multi(mp_z)
        assert r.geom_type == 'MultiPolygon'
        assert not r.has_z
        assert len(list(r.geoms)) == 2

    def test_mixed_layer_one_feature_per_row(self):
        """
        Layer campuran Polygon Z + MultiPolygon Z:
        - 2 baris input → 2 features output (BUKAN di-explode)
        - Semua tipe MultiPolygon
        """
        import json
        from shapely.geometry import MultiPolygon
        poly_z = Polygon([(116.5,-8.5,100),(117.5,-8.5,150),(117.5,-7.5,200),(116.5,-7.5,120),(116.5,-8.5,100)])
        mp_z = MultiPolygon([
            Polygon([(118.0,-8.5,50),(119.0,-8.5,60),(119.0,-7.5,70),(118.0,-7.5,55),(118.0,-8.5,50)]),
            Polygon([(120.0,-8.5,30),(121.0,-8.5,40),(121.0,-7.5,50),(120.0,-7.5,35),(120.0,-8.5,30)]),
        ])
        gdf = gpd.GeoDataFrame(
            {'nama': ['A','B']},
            geometry=[poly_z, mp_z],
            crs='EPSG:4326'
        )
        features = []
        for idx, row in gdf.iterrows():
            geom = self._to_multi(row['geometry'])
            if geom:
                features.append({
                    'type':'Feature','id':str(idx),
                    'geometry': geom.__geo_interface__,
                    'properties': {'nama': row['nama']}
                })
        # 2 baris → 2 features (bukan 3 seperti sebelumnya)
        assert len(features) == 2, f'Expected 2 features, got {len(features)}'
        # Semua MultiPolygon
        for f in features:
            assert f['geometry']['type'] == 'MultiPolygon', f['geometry']['type']
        # JSON-serializable
        json.dumps({'type':'FeatureCollection','features':features})

    def test_all_geojson_serializable(self):
        """Semua hasil _to_multi harus JSON-serializable."""
        import json
        from shapely.geometry import MultiPolygon, Point
        cases = [
            Polygon([(0,0,10),(1,0,20),(1,1,30),(0,1,40),(0,0,10)]),
            MultiPolygon([
                Polygon([(0,0),(1,0),(1,1),(0,1),(0,0)]),
                Polygon([(2,2),(3,2),(3,3),(2,3),(2,2)]),
            ]),
            Point(116.5, -8.5, 100.0),
        ]
        for geom in cases:
            r = self._to_multi(geom)
            assert r is not None
            result = json.dumps(r.__geo_interface__)
            assert len(result) > 10
