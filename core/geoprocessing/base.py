"""
core/geoprocessing/base.py — Abstract base for all geoprocessing operations
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.domain.value_objects import GeoprocessSpec


@dataclass
class GeoprocessResult:
    sql: str
    operation_name: str
    description: str = ""
    output_geom_col: str = "geom"


class BaseGeoprocess(ABC):
    """
    Abstract geoprocessing operation.
    Each subclass generates a PostGIS SQL string from a GeoprocessSpec.
    """

    name: str = ""              # Human-readable name, e.g. "Buffer"
    category: str = ""          # e.g. "Overlay", "Geometri"
    icon: str = "⚙"
    description: str = ""
    requires_overlay: bool = False   # True if needs a second layer

    @abstractmethod
    def build_sql(self, spec: GeoprocessSpec) -> str:
        """Generate the PostGIS SQL SELECT statement."""

    def execute(self, spec: GeoprocessSpec) -> GeoprocessResult:
        sql = self.build_sql(spec)
        return GeoprocessResult(
            sql=sql,
            operation_name=self.name,
            description=self.description,
        )

    # ── Shared helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _q(schema: str, table: str) -> str:
        return f'"{schema}"."{table}"'

    @staticmethod
    def _col(name: str) -> str:
        return f'"{name}"'

    @staticmethod
    def _union_overlay(schema: str, table: str, geom: str) -> str:
        """ST_Union of an entire overlay table — used for clip / difference."""
        return (f'(SELECT ST_Union({BaseGeoprocess._col(geom)}) AS "{geom}" '
                f'FROM {BaseGeoprocess._q(schema, table)})')

    @staticmethod
    def _match_srid(expr_a: str, expr_b: str) -> tuple:
        """
        Kembalikan (expr_a, expr_b) dimana expr_b sudah di-transform
        ke SRID yang sama dengan expr_a secara otomatis di runtime PostGIS.
        Menangani kasus dua layer dengan CRS berbeda (misal 4326 vs 3857).
        """
        expr_b_transformed = f"ST_Transform({expr_b}, ST_SRID({expr_a}))"
        return expr_a, expr_b_transformed
