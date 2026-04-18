"""
core/geoprocessing/buffer.py
Semua operasi geoprocessing — SQL builder yang benar secara teori spasial.

Prinsip utama:
  - Operasi berbasis jarak (Buffer, DWithin, Distance) HARUS transform ke
    CRS proyeksi (UTM/geography) agar satuan meter benar.
  - Pengukuran (Area, Length, Perimeter) menggunakan ::geography untuk
    akurasi ellipsoid, bukan ST_Transform ke 3857 (Web Mercator distorsi).
  - SRID dideteksi dari layer sumber via subquery, bukan hardcode.
"""

from core.geoprocessing.base import BaseGeoprocess
from core.domain.value_objects import GeoprocessSpec


# ── Helper: build geography-aware atau UTM-aware measurement ─────────────────

def _area_sql(gc: str, tbl: str, unit: str, srid: int = 0) -> str:
    """
    Hitung luas dengan akurasi maksimum:
    - Jika data sudah UTM (srid 326xx/327xx) → ST_Area langsung (sudah meter)
    - Selainnya → cast ke ::geography untuk akurasi ellipsoid WGS84
    """
    from utils.constants import AREA_UNITS
    div = AREA_UNITS.get(unit, 1)
    unit_col = unit.replace("²","2").replace(" ","_")

    # Jika sudah projected (UTM, dll) → ST_Area langsung sudah dalam m²
    # Jika geographic (4326, 4755) → pakai ::geography
    # Kita tidak tahu SRID saat build time, jadi pakai CASE di SQL
    return (
        f"SELECT *,\n"
        f"  CASE\n"
        f"    WHEN ST_SRID({gc}) IN (0, 4326, 4755, 4269, 4283)\n"
        f"      THEN ST_Area({gc}::geography) / {div}\n"
        f"    ELSE ST_Area({gc}) / {div}\n"
        f"  END AS area_{unit_col}\n"
        f"FROM {tbl}"
    )


def _length_sql(gc: str, tbl: str, col_name: str = "length_m") -> str:
    return (
        f"SELECT *,\n"
        f"  CASE\n"
        f"    WHEN ST_SRID({gc}) IN (0, 4326, 4755, 4269, 4283)\n"
        f"      THEN ST_Length({gc}::geography)\n"
        f"    ELSE ST_Length({gc})\n"
        f"  END AS {col_name}\n"
        f"FROM {{tbl}}"
    ).replace("{tbl}", tbl)


def _buffer_sql(gc: str, tbl: str, distance: float,
                segments: int, dissolve: bool) -> str:
    """
    Buffer dalam meter yang benar untuk semua CRS:
    - Data projected (UTM) → ST_Buffer langsung (unit sudah meter)
    - Data geographic (4326) → cast ke ::geography, buffer, cast balik ke geometry
      ST_Buffer(geom::geography, dist_meter)::geometry
    """
    # CASE di SQL agar benar untuk kedua jenis CRS
    buf_expr = (
        f"CASE\n"
        f"    WHEN ST_SRID({gc}) IN (0, 4326, 4755, 4269, 4283)\n"
        f"      THEN ST_Buffer({gc}::geography, {distance}, {segments})::geometry\n"
        f"    ELSE ST_Buffer({gc}, {distance}, {segments})\n"
        f"  END"
    )
    if dissolve:
        return f"SELECT ST_Union(\n  {buf_expr}\n) AS geom_buffer\nFROM {tbl}"
    return f"SELECT *,\n  {buf_expr} AS geom_buffer\nFROM {tbl}"


def _dwithin_sql(a: str, ga: str, b: str, gb: str, distance: float) -> str:
    """
    ST_DWithin dalam meter yang benar untuk semua CRS.
    - Geographic → ST_DWithin(geom::geography, geom::geography, meter)
    - Projected → ST_DWithin(geom, geom, meter) langsung
    """
    return (
        f"SELECT DISTINCT a.*\nFROM {a} a\n"
        f"WHERE EXISTS (\n"
        f"  SELECT 1 FROM {b} b\n"
        f"  WHERE\n"
        f"    CASE\n"
        f"      WHEN ST_SRID(a.{ga}) IN (0, 4326, 4755, 4269, 4283)\n"
        f"        THEN ST_DWithin(a.{ga}::geography, b.{gb}::geography, {distance})\n"
        f"      ELSE ST_DWithin(a.{ga}, b.{gb}, {distance})\n"
        f"    END\n"
        f")"
    )


def _distance_sql(ga: str, gb: str) -> str:
    """ST_Distance dalam meter, benar untuk geographic dan projected."""
    return (
        f"CASE\n"
        f"      WHEN ST_SRID(a.{ga}) IN (0, 4326, 4755, 4269, 4283)\n"
        f"        THEN ST_Distance(a.{ga}::geography, b.{gb}::geography)\n"
        f"      ELSE ST_Distance(a.{ga}, b.{gb})\n"
        f"    END"
    )


# ──────────────────────────────────────────────────────────────────────────────
# OVERLAY
# ──────────────────────────────────────────────────────────────────────────────

class Buffer(BaseGeoprocess):
    name = "Buffer"
    category = "Overlay"
    icon = "⭕"
    description = "Buat zona penyangga (buffer) di sekitar geometri — jarak dalam meter"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        return _buffer_sql(gc, tbl, spec.distance, spec.segments, spec.dissolve)


class Intersect(BaseGeoprocess):
    name = "Intersect"
    category = "Overlay"
    icon = "⊗"
    description = "Ambil area irisan antara dua layer"
    requires_overlay = True

    def build_sql(self, spec: GeoprocessSpec) -> str:
        a  = self._q(spec.input_schema, spec.input_table)
        b  = self._q(spec.overlay_schema, spec.overlay_table)
        ga = self._col(spec.input_geom)
        gb = self._col(spec.overlay_geom)
        # ST_Transform b ke SRID a — tangani beda CRS antar layer
        eb = f"ST_Transform(b.{gb}, ST_SRID(a.{ga}))"
        return (
            f"SELECT\n"
            f"  a.*,\n"
            f"  ST_Intersection(a.{ga}, {eb}) AS geom_intersection\n"
            f"FROM {a} a\n"
            f"JOIN {b} b ON ST_Intersects(a.{ga}, {eb})\n"
            f"WHERE NOT ST_IsEmpty(ST_Intersection(a.{ga}, {eb}))"
        )


class Union(BaseGeoprocess):
    name = "Union"
    category = "Overlay"
    icon = "⊕"
    description = "Gabungkan semua geometri dalam satu layer"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        if spec.dissolve_field:
            df = self._col(spec.dissolve_field)
            return (
                f"SELECT {df}, ST_Union({gc}) AS geom_union\n"
                f"FROM {tbl}\nGROUP BY {df}"
            )
        return f"SELECT ST_Union({gc}) AS geom_union FROM {tbl}"


class Clip(BaseGeoprocess):
    name = "Clip"
    category = "Overlay"
    icon = "✂"
    description = "Potong layer input dengan batas layer clipper"
    requires_overlay = True

    def build_sql(self, spec: GeoprocessSpec) -> str:
        a  = self._q(spec.input_schema, spec.input_table)
        ga = self._col(spec.input_geom)
        gb = self._col(spec.overlay_geom)
        ov = self._union_overlay(
            spec.overlay_schema, spec.overlay_table, spec.overlay_geom)
        eb = f"ST_Transform(b.{gb}, ST_SRID(a.{ga}))"
        return (
            f"SELECT a.*,\n"
            f"  ST_Intersection(a.{ga}, {eb}) AS geom_clipped\n"
            f"FROM {a} a,\n"
            f"  {ov} b\n"
            f"WHERE ST_Intersects(a.{ga}, {eb})\n"
            f"  AND NOT ST_IsEmpty(ST_Intersection(a.{ga}, {eb}))"
        )


class Difference(BaseGeoprocess):
    name = "Difference"
    category = "Overlay"
    icon = "⊖"
    description = "Ambil bagian layer input yang tidak tumpang tindih dengan layer penghapus"
    requires_overlay = True

    def build_sql(self, spec: GeoprocessSpec) -> str:
        a  = self._q(spec.input_schema, spec.input_table)
        ga = self._col(spec.input_geom)
        gb = self._col(spec.overlay_geom)
        ov = self._union_overlay(
            spec.overlay_schema, spec.overlay_table, spec.overlay_geom)
        eb = f"ST_Transform(b.{gb}, ST_SRID(a.{ga}))"
        return (
            f"SELECT a.*,\n"
            f"  ST_Difference(a.{ga}, {eb}) AS geom_diff\n"
            f"FROM {a} a,\n"
            f"  {ov} b\n"
            f"WHERE NOT ST_IsEmpty(ST_Difference(a.{ga}, {eb}))"
        )


class SymDifference(BaseGeoprocess):
    name = "Symmetric Difference"
    category = "Overlay"
    icon = "△"
    description = "Area yang ada di salah satu layer tapi tidak di keduanya"
    requires_overlay = True

    def build_sql(self, spec: GeoprocessSpec) -> str:
        # SymDifference yang benar: union kedua layer MINUS intersection
        # Bukan cartesian product antar fitur
        a  = self._q(spec.input_schema, spec.input_table)
        b  = self._q(spec.overlay_schema, spec.overlay_table)
        ga = self._col(spec.input_geom)
        gb = self._col(spec.overlay_geom)
        return (
            f"SELECT ST_SymDifference(\n"
            f"  (SELECT ST_Union({ga}) FROM {a}),\n"
            f"  (SELECT ST_Transform(ST_Union({gb}),"
            f"   (SELECT ST_SRID({ga}) FROM {a} LIMIT 1)) FROM {b})\n"
            f") AS geom_symdiff"
        )


# ──────────────────────────────────────────────────────────────────────────────
# GEOMETRY
# ──────────────────────────────────────────────────────────────────────────────

class Centroid(BaseGeoprocess):
    name = "Centroid"
    category = "Geometri"
    icon = "⊙"
    description = "Titik pusat geometri (gunakan Point on Surface untuk polygon konkaf)"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        return f"SELECT *, ST_Centroid({gc}) AS geom_centroid FROM {tbl}"


class PointOnSurface(BaseGeoprocess):
    name = "Point on Surface"
    category = "Geometri"
    icon = "📌"
    description = "Titik yang selalu berada di dalam polygon (lebih aman dari Centroid)"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        return f"SELECT *, ST_PointOnSurface({gc}) AS geom_point_on_surface FROM {tbl}"


class ConvexHull(BaseGeoprocess):
    name = "Convex Hull"
    category = "Geometri"
    icon = "🔷"
    description = "Buat cangkang cembung (convex hull)"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        return f"SELECT *, ST_ConvexHull({gc}) AS geom_hull FROM {tbl}"


class Envelope(BaseGeoprocess):
    name = "Envelope"
    category = "Geometri"
    icon = "⬜"
    description = "Buat bounding box tiap fitur"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        return f"SELECT *, ST_Envelope({gc}) AS geom_envelope FROM {tbl}"


class Simplify(BaseGeoprocess):
    name = "Simplify"
    category = "Geometri"
    icon = "〰"
    description = "Sederhanakan geometri — toleransi dalam unit CRS layer"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        fn  = "ST_SimplifyPreserveTopology" if spec.preserve_topology else "ST_Simplify"
        return (
            f"-- Toleransi {spec.tolerance} dalam unit CRS layer\n"
            f"-- Untuk EPSG:4326 (derajat): 0.001° ≈ 111 m\n"
            f"-- Untuk EPSG:32750 (meter) : 1.0 = 1 m\n"
            f"SELECT *, {fn}({gc}, {spec.tolerance}) AS geom_simplified\n"
            f"FROM {tbl}"
        )


class Dissolve(BaseGeoprocess):
    name = "Dissolve"
    category = "Geometri"
    icon = "🫧"
    description = "Gabungkan geometri berdasarkan field atribut"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        if spec.dissolve_field:
            df = self._col(spec.dissolve_field)
            return (
                f"SELECT {df},\n"
                f"  ST_Union({gc}) AS geom_dissolved\n"
                f"FROM {tbl}\n"
                f"GROUP BY {df}"
            )
        return f"SELECT ST_Union({gc}) AS geom_dissolved FROM {tbl}"


class Reproject(BaseGeoprocess):
    name = "Reproject"
    category = "Geometri"
    icon = "🌐"
    description = "Transformasi sistem koordinat (EPSG)"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        return (
            f"SELECT *,\n"
            f"  ST_Transform({gc}, {spec.target_srid}) AS geom_reproj\n"
            f"FROM {tbl}"
        )


class Voronoi(BaseGeoprocess):
    name = "Voronoi"
    category = "Geometri"
    icon = "🕸"
    description = "Buat diagram Voronoi dari kumpulan titik"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        return (
            f"SELECT (ST_Dump(\n"
            f"  ST_VoronoiPolygons(ST_Collect({gc}))\n"
            f")).geom AS geom_voronoi\n"
            f"FROM {tbl}"
        )


class Delaunay(BaseGeoprocess):
    name = "Delaunay"
    category = "Geometri"
    icon = "◬"
    description = "Triangulasi Delaunay dari kumpulan titik"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        return (
            f"SELECT (ST_Dump(\n"
            f"  ST_DelaunayTriangles(ST_Collect({gc}))\n"
            f")).geom AS geom_delaunay\n"
            f"FROM {tbl}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# MEASUREMENT — akurat secara geodesi
# ──────────────────────────────────────────────────────────────────────────────

class CalculateArea(BaseGeoprocess):
    name = "Hitung Luas"
    category = "Kalkulasi"
    icon = "📐"
    description = "Hitung luas — akurat di ellipsoid WGS84 (bukan Web Mercator)"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        from utils.constants import AREA_UNITS
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        div = AREA_UNITS.get(spec.area_unit, 1)
        unit_col = spec.area_unit.replace("²","2").replace(" ","_")
        # Geography cast: akurat di ellipsoid untuk data geografis
        # ST_Area langsung: akurat untuk data yang sudah projected (UTM)
        return (
            f"SELECT *,\n"
            f"  CASE\n"
            f"    WHEN ST_SRID({gc}) IN (0, 4326, 4755, 4269, 4283, 4758)\n"
            f"      THEN ST_Area({gc}::geography) / {div}\n"
            f"    ELSE ST_Area({gc}) / {div}\n"
            f"  END AS area_{unit_col}\n"
            f"FROM {tbl}"
        )


class CalculateLength(BaseGeoprocess):
    name = "Hitung Panjang"
    category = "Kalkulasi"
    icon = "📏"
    description = "Hitung panjang geometri dalam meter — akurat di ellipsoid"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        return (
            f"SELECT *,\n"
            f"  CASE\n"
            f"    WHEN ST_SRID({gc}) IN (0, 4326, 4755, 4269, 4283, 4758)\n"
            f"      THEN ST_Length({gc}::geography)\n"
            f"    ELSE ST_Length({gc})\n"
            f"  END AS length_m\n"
            f"FROM {tbl}"
        )


class CalculatePerimeter(BaseGeoprocess):
    name = "Hitung Perimeter"
    category = "Kalkulasi"
    icon = "🔲"
    description = "Hitung keliling geometri dalam meter — akurat di ellipsoid"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        gc  = self._col(spec.input_geom)
        tbl = self._q(spec.input_schema, spec.input_table)
        return (
            f"SELECT *,\n"
            f"  CASE\n"
            f"    WHEN ST_SRID({gc}) IN (0, 4326, 4755, 4269, 4283, 4758)\n"
            f"      THEN ST_Perimeter({gc}::geography)\n"
            f"    ELSE ST_Perimeter({gc})\n"
            f"  END AS perimeter_m\n"
            f"FROM {tbl}"
        )


class SpatialStats(BaseGeoprocess):
    name = "Statistik Spasial"
    category = "Kalkulasi"
    icon = "📊"
    description = "Hitung statistik atribut numerik per kelompok"
    requires_overlay = False

    def build_sql(self, spec: GeoprocessSpec) -> str:
        tbl = self._q(spec.input_schema, spec.input_table)
        vc  = self._col(spec.value_col or "1")
        if spec.group_col:
            gc = self._col(spec.group_col)
            return (
                f"SELECT {gc},\n"
                f"  COUNT(*)        AS count_features,\n"
                f"  SUM({vc})       AS total,\n"
                f"  AVG({vc})       AS average,\n"
                f"  MIN({vc})       AS minimum,\n"
                f"  MAX({vc})       AS maximum,\n"
                f"  STDDEV({vc})    AS std_dev\n"
                f"FROM {tbl}\n"
                f"GROUP BY {gc}"
            )
        return (
            f"SELECT\n"
            f"  COUNT(*)        AS count_features,\n"
            f"  SUM({vc})       AS total,\n"
            f"  AVG({vc})       AS average,\n"
            f"  MIN({vc})       AS minimum,\n"
            f"  MAX({vc})       AS maximum,\n"
            f"  STDDEV({vc})    AS std_dev\n"
            f"FROM {tbl}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# SPATIAL SELECTION — jarak dalam meter yang benar
# ──────────────────────────────────────────────────────────────────────────────

class SelectByLocation(BaseGeoprocess):
    name = "Select by Location"
    category = "Seleksi Spasial"
    icon = "📍"
    description = "Pilih fitur berdasarkan relasi spasial dengan layer lain"
    requires_overlay = True

    def build_sql(self, spec: GeoprocessSpec) -> str:
        a    = self._q(spec.input_schema, spec.input_table)
        b    = self._q(spec.overlay_schema, spec.overlay_table)
        ga   = self._col(spec.input_geom)
        gb   = self._col(spec.overlay_geom)
        pred = spec.spatial_predicate
        eb = f"ST_Transform(b.{gb}, ST_SRID(a.{ga}))"
        return (
            f"SELECT DISTINCT a.*\n"
            f"FROM {a} a\n"
            f"WHERE EXISTS (\n"
            f"  SELECT 1 FROM {b} b\n"
            f"  WHERE {pred}(a.{ga}, {eb})\n"
            f")"
        )


class SelectByDistance(BaseGeoprocess):
    name = "Select by Distance"
    category = "Seleksi Spasial"
    icon = "📡"
    description = "Pilih fitur dalam radius jarak tertentu (meter)"
    requires_overlay = True

    def build_sql(self, spec: GeoprocessSpec) -> str:
        a  = self._q(spec.input_schema, spec.input_table)
        b  = self._q(spec.overlay_schema, spec.overlay_table)
        ga = self._col(spec.input_geom)
        gb = self._col(spec.overlay_geom)
        # Jarak selalu dalam meter — geography cast untuk CRS geografis
        return _dwithin_sql(a, ga, b, gb, spec.distance)


class NearestNeighbor(BaseGeoprocess):
    name = "Nearest Neighbor"
    category = "Seleksi Spasial"
    icon = "🎯"
    description = "Cari K fitur terdekat — jarak hasil dalam meter"
    requires_overlay = True

    def build_sql(self, spec: GeoprocessSpec) -> str:
        a  = self._q(spec.input_schema, spec.input_table)
        b  = self._q(spec.overlay_schema, spec.overlay_table)
        ga = self._col(spec.input_geom)
        gb = self._col(spec.overlay_geom)
        dist = _distance_sql(ga, gb)
        # KNN operator <-> butuh SRID sama, transform b ke SRID a
        return (
            f"SELECT DISTINCT ON (a.ctid) a.*, b.*,\n"
            f"  {dist} AS dist_m\n"
            f"FROM {a} a\n"
            f"CROSS JOIN LATERAL (\n"
            f"  SELECT * FROM {b}\n"
            f"  ORDER BY ST_Transform({gb}, ST_SRID(a.{ga})) <-> a.{ga}\n"
            f"  LIMIT {spec.k_neighbors}\n"
            f") b\n"
            f"ORDER BY a.ctid, dist_m"
        )


# ──────────────────────────────────────────────────────────────────────────────
# SPATIAL JOIN
# ──────────────────────────────────────────────────────────────────────────────

class SpatialJoin(BaseGeoprocess):
    name = "Spatial Join"
    category = "Gabung"
    icon = "🔗"
    description = "Gabung atribut dua layer berdasarkan relasi spasial"
    requires_overlay = True

    def build_sql(self, spec: GeoprocessSpec) -> str:
        a  = self._q(spec.input_schema, spec.input_table)
        b  = self._q(spec.overlay_schema, spec.overlay_table)
        ga = self._col(spec.input_geom)
        gb = self._col(spec.overlay_geom)
        # Prefix kolom b dengan 'b_' untuk hindari konflik nama
        return (
            f"SELECT a.*,\n"
            f"  b.* -- Catatan: rename kolom b jika ada konflik nama dengan a\n"
            f"FROM {a} a\n"
            f"{spec.join_type} JOIN {b} b\n"
            f"  ON {spec.spatial_predicate}(a.{ga}, ST_Transform(b.{gb}, ST_SRID(a.{ga})))"
        )


# ── JOIN BY FIELD ─────────────────────────────────────────────────────────────

class JoinByField(BaseGeoprocess):
    """
    Gabungkan atribut dua tabel berdasarkan nilai kolom yang sama (non-spasial).
    Cocok untuk menggabungkan layer spasial dengan tabel atribut (CSV non-spasial).
    """
    name = "Join by Field"
    category = "Gabung"
    icon = "🔑"
    description = "Gabung atribut berdasarkan kesamaan nilai kolom (non-spasial)"
    requires_overlay = True

    def build_sql(self, spec: GeoprocessSpec) -> str:
        a   = self._q(spec.input_schema, spec.input_table)
        b   = self._q(spec.overlay_schema, spec.overlay_table)
        lf  = self._col(spec.join_left_field or "id")
        rf  = self._col(spec.join_right_field or "id")
        jt  = spec.join_type or "LEFT OUTER"
        rft = (spec.join_right_field or "id").strip('"')
        # Kolom b diambil semua KECUALI kolom join key (rf) karena sudah ada di a.
        # Kolom lain yang namanya sama dengan kolom a akan diberi prefix 'b_'
        # melalui teknik USING — jika kolom join key namanya sama, USING menghilangkan duplikat.
        # Jika nama kolom kiri == kanan, pakai USING untuk auto-dedup:
        lft = (spec.join_left_field or "id").strip('"')
        if lft == rft:
            return (
                f"-- Join menggunakan kolom '{lft}' (nama sama di kedua tabel — pakai USING)\n"
                f"SELECT * FROM {a} a\n"
                f"{jt} JOIN {b} b USING ({self._col(lft)})"
            )
        else:
            return (
                f"-- Join kolom '{lft}' (input) = '{rft}' (join table)\n"
                f"-- Kolom b dengan nama sama dengan a akan ada dua versi di hasil\n"
                f"SELECT a.*, b.* FROM {a} a\n"
                f"{jt} JOIN {b} b ON a.{lf} = b.{rf}"
            )
