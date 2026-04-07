"""
core/services/query_service.py
Executes attribute queries (QuerySpec) and raw SQL.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import geopandas as gpd

from core.database.repository import LayerRepository
from core.domain.value_objects import QuerySpec
from utils.logger import get_logger

logger = get_logger("spaque.services.query")


class QueryResult:
    __slots__ = ("gdf", "columns", "rows", "row_count", "error", "sql")

    def __init__(self, gdf, columns, rows, sql, error=""):
        self.gdf: Optional[gpd.GeoDataFrame] = gdf
        self.columns: List[str] = columns
        self.rows: List = rows
        self.row_count: int = len(rows)
        self.sql: str = sql
        self.error: str = error

    @property
    def has_error(self) -> bool:
        return bool(self.error)

    @property
    def has_geometry(self) -> bool:
        return self.gdf is not None


class QueryService:

    def __init__(self, repo: LayerRepository):
        self._repo = repo

    def execute_spec(self, spec: QuerySpec,
                     geom_col: Optional[str] = None) -> QueryResult:
        """Execute a QuerySpec."""
        sql = spec.build_sql()
        return self.execute_sql(sql, geom_col)

    def execute_sql(self, sql: str,
                    geom_col: Optional[str] = None) -> QueryResult:
        """Execute arbitrary SQL."""
        logger.info("Executing SQL: %.120s", sql)
        try:
            gdf, cols, rows = self._repo.execute_sql(sql, geom_col)
            logger.info("Query OK: %d rows", len(rows))
            return QueryResult(gdf, cols, rows, sql)
        except Exception as exc:
            logger.error("Query failed: %s", exc)
            return QueryResult(None, [], [], sql, error=str(exc))
