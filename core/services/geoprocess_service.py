"""
core/services/geoprocess_service.py
Runs geoprocessing specs and persists results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import geopandas as gpd

from core.database.repository import LayerRepository
from core.domain.value_objects import GeoprocessSpec
from core.geoprocessing.factory import GeoprocessFactory
from core.geoprocessing.exceptions import GeoprocessError, MissingLayerError
from utils.logger import get_logger

logger = get_logger("spaque.services.geoprocess")


@dataclass
class GeoprocessResult:
    success: bool
    message: str
    sql: str
    output_table: str
    output_schema: str
    row_count: int = 0
    gdf: Optional[gpd.GeoDataFrame] = None

    @property
    def has_error(self) -> bool:
        return not self.success


class GeoprocessService:

    def __init__(self, repo: LayerRepository):
        self._repo = repo

    def run(self, spec: GeoprocessSpec) -> GeoprocessResult:
        """
        1. Build SQL via factory
        2. Persist to output table
        3. Load result as GeoDataFrame
        """
        op = GeoprocessFactory.get(spec.operation)
        if not op:
            return GeoprocessResult(
                success=False,
                message=f"Operasi tidak dikenal: {spec.operation}",
                sql="", output_table=spec.output_table,
                output_schema=spec.output_schema,
            )

        # Validate required overlay
        if op.requires_overlay and not spec.overlay_table:
            return GeoprocessResult(
                success=False,
                message=f"Operasi '{spec.operation}' memerlukan layer kedua (overlay).",
                sql="", output_table=spec.output_table,
                output_schema=spec.output_schema,
            )

        try:
            result = op.execute(spec)
            sql = result.sql
        except Exception as exc:
            logger.error("SQL build failed: %s", exc)
            return GeoprocessResult(
                success=False, message=str(exc), sql="",
                output_table=spec.output_table, output_schema=spec.output_schema,
            )

        # Persist
        ok, msg, count = self._repo.save_geoprocess_result(
            sql, spec.output_schema, spec.output_table
        )
        if not ok:
            return GeoprocessResult(
                success=False, message=msg, sql=sql,
                output_table=spec.output_table, output_schema=spec.output_schema,
            )

        # Reload as GDF
        load_sql = f'SELECT * FROM "{spec.output_schema}"."{spec.output_table}"'
        gdf, cols, rows = self._repo.execute_sql(load_sql)

        self._repo.invalidate_cache()

        logger.info("Geoprocess '%s' done: %d features → %s.%s",
                    spec.operation, count, spec.output_schema, spec.output_table)

        return GeoprocessResult(
            success=True, message=msg, sql=sql,
            output_table=spec.output_table, output_schema=spec.output_schema,
            row_count=count, gdf=gdf,
        )
