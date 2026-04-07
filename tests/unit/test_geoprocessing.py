"""
tests/unit/test_geoprocessing.py — Unit tests for SQL builders
"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from core.domain.value_objects import GeoprocessSpec, QuerySpec, WhereCondition
from core.geoprocessing.factory import GeoprocessFactory


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_spec(**kwargs) -> GeoprocessSpec:
    defaults = dict(
        operation="Buffer",
        input_schema="public",
        input_table="kawasan",
        input_geom="geom",
        output_table="hasil",
        output_schema="public",
        distance=500.0,
        segments=16,
    )
    defaults.update(kwargs)
    return GeoprocessSpec(**defaults)


# ── Geoprocessing SQL tests ───────────────────────────────────────────────────

class TestBuffer:
    def test_basic_buffer(self):
        spec = make_spec(operation="Buffer", distance=500, dissolve=False)
        op = GeoprocessFactory.get("Buffer")
        sql = op.build_sql(spec)
        assert "ST_Buffer" in sql
        assert "500" in sql
        assert '"geom"' in sql

    def test_dissolved_buffer(self):
        spec = make_spec(operation="Buffer", distance=100, dissolve=True)
        op = GeoprocessFactory.get("Buffer")
        sql = op.build_sql(spec)
        assert "ST_Union" in sql
        assert "ST_Buffer" in sql


class TestIntersect:
    def test_intersect_sql(self):
        spec = make_spec(
            operation="Intersect",
            overlay_schema="public",
            overlay_table="batas_desa",
            overlay_geom="geom",
        )
        op = GeoprocessFactory.get("Intersect")
        sql = op.build_sql(spec)
        assert "ST_Intersection" in sql
        assert "ST_Intersects" in sql
        assert "batas_desa" in sql


class TestCentroid:
    def test_centroid_sql(self):
        op = GeoprocessFactory.get("Centroid")
        sql = op.build_sql(make_spec(operation="Centroid"))
        assert "ST_Centroid" in sql


class TestCalculateArea:
    def test_area_ha(self):
        spec = make_spec(operation="Hitung Luas", area_unit="ha")
        op = GeoprocessFactory.get("Hitung Luas")
        sql = op.build_sql(spec)
        assert "ST_Area" in sql
        assert "10000" in sql

    def test_area_km2(self):
        spec = make_spec(operation="Hitung Luas", area_unit="km²")
        op = GeoprocessFactory.get("Hitung Luas")
        sql = op.build_sql(spec)
        assert "1000000" in sql


class TestFactory:
    def test_all_operations_buildable(self):
        """Every registered operation should build SQL without error."""
        for op in GeoprocessFactory.all_operations():
            spec = make_spec(
                operation=op.name,
                overlay_schema="public",
                overlay_table="overlay_tbl",
                overlay_geom="geom",
            )
            try:
                sql = op.build_sql(spec)
                assert isinstance(sql, str) and len(sql) > 10
            except Exception as exc:
                pytest.fail(f"Operation '{op.name}' failed to build SQL: {exc}")


# ── QuerySpec tests ───────────────────────────────────────────────────────────

class TestQuerySpec:
    def test_simple_select(self):
        spec = QuerySpec(schema="public", table="pohon")
        sql = spec.build_sql()
        assert 'FROM "public"."pohon"' in sql
        assert "SELECT *" in sql

    def test_single_condition(self):
        spec = QuerySpec(
            schema="public", table="pohon",
            conditions=[WhereCondition("dbh", ">=", "30", "AND")],
        )
        sql = spec.build_sql()
        assert "WHERE" in sql
        assert '"dbh" >= 30' in sql

    def test_multiple_conditions(self):
        spec = QuerySpec(
            schema="public", table="pohon",
            conditions=[
                WhereCondition("dbh", ">=", "30", "AND"),
                WhereCondition("jenis", "LIKE", "jati%", "OR"),
            ],
        )
        sql = spec.build_sql()
        assert "WHERE" in sql
        assert "OR" in sql

    def test_null_condition(self):
        spec = QuerySpec(
            schema="public", table="pohon",
            conditions=[WhereCondition("catatan", "IS NULL", "", "AND")],
        )
        sql = spec.build_sql()
        assert "IS NULL" in sql

    def test_between_condition(self):
        cond = WhereCondition("tinggi", "BETWEEN", "10, 30", "AND")
        sql = cond.to_sql()
        assert "BETWEEN 10 AND 30" in sql

    def test_in_condition(self):
        cond = WhereCondition("kode", "IN", "'A','B','C'", "AND")
        sql = cond.to_sql()
        assert "IN (" in sql

    def test_order_and_limit(self):
        spec = QuerySpec(
            schema="public", table="pohon",
            order_col="dbh", order_dir="DESC", limit=100,
        )
        sql = spec.build_sql()
        assert "ORDER BY" in sql
        assert "LIMIT 100" in sql


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
