"""
core/database/repository.py — Repository pattern abstraction
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import geopandas as gpd

from core.database.postgis import PostGISDatabase
from core.domain.entities.layer import LayerInfo, LayerColumn
from utils.logger import get_logger

logger = get_logger("spaque.db.repository")


class LayerRepository:
    """
    High-level data access object for spatial layers.
    Delegates to PostGISDatabase; adds caching.
    """

    def __init__(self, postgis: PostGISDatabase):
        self._postgis = postgis
        self._layer_cache: List[LayerInfo] = []
        self._column_cache: dict = {}   # qualified_name -> List[LayerColumn]

    def all_layers(self, refresh: bool = False) -> List[LayerInfo]:
        if not self._layer_cache or refresh:
            self._layer_cache = self._postgis.list_spatial_layers()
            self._column_cache.clear()
        return self._layer_cache

    def columns_for(self, layer: LayerInfo,
                    refresh: bool = False) -> List[LayerColumn]:
        key = layer.qualified_name
        if key not in self._column_cache or refresh:
            self._column_cache[key] = self._postgis.get_layer_columns(layer)
        return self._column_cache[key]

    def row_count(self, layer: LayerInfo) -> int:
        return self._postgis.get_row_count(layer)

    def load_geodataframe(self, layer: LayerInfo,
                          limit: int = 5000) -> Optional[gpd.GeoDataFrame]:
        sql = f"SELECT * FROM {layer.qualified_name} LIMIT {limit}"
        return self._postgis.fetch_geodataframe(sql, geom_col=layer.geom_col)

    def execute_sql(self, sql: str,
                    geom_col: Optional[str] = None
                    ) -> Tuple[Optional[gpd.GeoDataFrame], List[str], List[tuple]]:
        """
        Smart execution: tries GeoDataFrame first, falls back to raw rows.
        Returns (gdf_or_None, columns, rows).
        """
        gdf = self._postgis.fetch_geodataframe(sql, geom_col)
        if gdf is not None:
            cols = list(gdf.columns)
            rows = gdf.head(5000).values.tolist()
            return gdf, cols, rows
        # Fallback
        cols, rows = self._postgis.fetch_raw(sql)
        return None, cols, rows

    def save_geoprocess_result(self, sql: str, schema: str,
                               table: str) -> Tuple[bool, str, int]:
        return self._postgis.create_table_from_sql(sql, schema, table)

    def invalidate_cache(self):
        self._layer_cache.clear()
        self._column_cache.clear()
