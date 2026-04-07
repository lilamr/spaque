"""
core/domain/entities/feature.py — Feature entity
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Feature:
    """A single geographic feature with attributes and geometry."""
    fid: Optional[Any]
    attributes: Dict[str, Any] = field(default_factory=dict)
    geometry_wkt: Optional[str] = None
    geometry_geojson: Optional[str] = None

    def get(self, col: str, default: Any = None) -> Any:
        return self.attributes.get(col, default)

    @property
    def attribute_count(self) -> int:
        return len(self.attributes)
