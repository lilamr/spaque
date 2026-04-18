"""
core/geoprocessing/factory.py — Registry & factory for all geoprocessing ops
"""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from core.geoprocessing.base import BaseGeoprocess
from core.geoprocessing.buffer import (
    Buffer, Intersect, Union, Clip, Difference, SymDifference,
    Centroid, PointOnSurface, ConvexHull, Envelope, Simplify,
    Dissolve, Reproject, Voronoi, Delaunay,
    CalculateArea, CalculateLength, CalculatePerimeter, SpatialStats,
    SelectByLocation, SelectByDistance, NearestNeighbor,
    SpatialJoin, JoinByField,
)

REGISTRY: Dict[str, List[Type[BaseGeoprocess]]] = {
    "Overlay":        [Buffer, Intersect, Union, Clip, Difference, SymDifference],
    "Geometri":       [Centroid, PointOnSurface, ConvexHull, Envelope,
                       Simplify, Dissolve, Reproject, Voronoi, Delaunay],
    "Kalkulasi":      [CalculateArea, CalculateLength, CalculatePerimeter, SpatialStats],
    "Seleksi Spasial":[SelectByLocation, SelectByDistance, NearestNeighbor],
    "Gabung":         [SpatialJoin, JoinByField],
}

# Flat name → instance map for quick lookup
_INSTANCES: Dict[str, BaseGeoprocess] = {
    cls.name: cls()
    for ops in REGISTRY.values()
    for cls in ops
}


class GeoprocessFactory:
    """
    Factory / registry for geoprocessing operations.
    """

    @staticmethod
    def all_categories() -> List[str]:
        return list(REGISTRY.keys())

    @staticmethod
    def operations_for(category: str) -> List[BaseGeoprocess]:
        return [cls() for cls in REGISTRY.get(category, [])]

    @staticmethod
    def get(name: str) -> Optional[BaseGeoprocess]:
        return _INSTANCES.get(name)

    @staticmethod
    def all_operations() -> List[BaseGeoprocess]:
        return list(_INSTANCES.values())

    @staticmethod
    def flat_registry() -> Dict[str, List[BaseGeoprocess]]:
        """Returns {category: [instances]}."""
        return {
            cat: [cls() for cls in ops]
            for cat, ops in REGISTRY.items()
        }
