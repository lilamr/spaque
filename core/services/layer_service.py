"""
core/services/layer_service.py
Orchestrates layer discovery, metadata, and data loading.
"""

from __future__ import annotations

from typing import List, Optional

import geopandas as gpd

from core.database.repository import LayerRepository
from core.domain.entities.layer import LayerInfo, LayerColumn
from utils.logger import get_logger

logger = get_logger("spaque.services.layer")


class LayerService:

    def __init__(self, repo: LayerRepository):
        self._repo = repo

    def refresh_layers(self) -> List[LayerInfo]:
        """Reload layer list from database."""
        layers = self._repo.all_layers(refresh=True)
        logger.info("Loaded %d spatial layers", len(layers))
        return layers

    def get_layers(self) -> List[LayerInfo]:
        return self._repo.all_layers()

    def get_columns(self, layer: LayerInfo) -> List[LayerColumn]:
        return self._repo.columns_for(layer)

    def get_numeric_columns(self, layer: LayerInfo) -> List[LayerColumn]:
        return [c for c in self.get_columns(layer) if c.is_numeric]

    def get_non_geom_columns(self, layer: LayerInfo) -> List[LayerColumn]:
        return [c for c in self.get_columns(layer) if not c.is_geometry]

    def get_text_columns(self, layer: LayerInfo) -> List[LayerColumn]:
        return [c for c in self.get_columns(layer) if c.is_text]

    def load_layer(self, layer: LayerInfo,
                   limit: int = 5000) -> Optional[gpd.GeoDataFrame]:
        logger.info("Loading layer %s (limit=%d)", layer.full_label, limit)
        return self._repo.load_geodataframe(layer, limit)

    def get_row_count(self, layer: LayerInfo) -> int:
        return self._repo.row_count(layer)

    def layer_by_name(self, schema: str, table: str) -> Optional[LayerInfo]:
        for layer in self._repo.all_layers():
            if layer.schema == schema and layer.table_name == table:
                return layer
        return None
