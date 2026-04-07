"""
core/domain/entities/layer.py — Layer entity (immutable value-like)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class LayerInfo:
    """
    Represents a single spatial layer (table) from PostGIS.
    Immutable after construction.
    """
    schema: str
    table_name: str
    geom_col: str
    geom_type: str          # e.g. "POLYGON", "MULTIPOLYGON"
    srid: int
    col_count: int = 0
    row_count: Optional[int] = None

    # ── Computed helpers ──────────────────────────────────────────────────────
    @property
    def qualified_name(self) -> str:
        return f'"{self.schema}"."{self.table_name}"'

    @property
    def display_name(self) -> str:
        return self.table_name

    @property
    def full_label(self) -> str:
        return f"{self.schema}.{self.table_name}"

    @property
    def geom_family(self) -> str:
        """Returns base type without MULTI prefix."""
        return self.geom_type.upper().replace("MULTI", "").split("(")[0]

    @property
    def is_polygon(self) -> bool:
        return "POLYGON" in self.geom_type.upper()

    @property
    def is_line(self) -> bool:
        return "LINE" in self.geom_type.upper()

    @property
    def is_point(self) -> bool:
        return "POINT" in self.geom_type.upper()

    def tooltip(self) -> str:
        parts = [
            f"Schema: {self.schema}",
            f"Tabel: {self.table_name}",
            f"Geometri: {self.geom_type}",
            f"SRID: {self.srid}",
            f"Kolom geometri: {self.geom_col}",
        ]
        if self.row_count is not None:
            parts.append(f"Jumlah fitur: {self.row_count:,}")
        return "\n".join(parts)


@dataclass
class LayerColumn:
    """Describes a single column of a layer."""
    name: str
    data_type: str
    udt_name: str

    @property
    def is_geometry(self) -> bool:
        return self.udt_name == "geometry"

    @property
    def is_numeric(self) -> bool:
        from utils.helpers import is_numeric_type
        return is_numeric_type(self.data_type)

    @property
    def is_text(self) -> bool:
        return self.data_type in (
            "text", "character varying", "varchar", "char", "character"
        )
