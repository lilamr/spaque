"""
core/domain/value_objects/__init__.py
Immutable value objects used across the domain.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ConnectionParams:
    host: str
    port: int
    dbname: str
    user: str
    password: str

    @property
    def safe_label(self) -> str:
        return f"{self.user}@{self.host}:{self.port}/{self.dbname}"


@dataclass(frozen=True)
class WhereCondition:
    column: str
    operator: str
    value: str
    logic: str = "AND"

    def to_sql(self) -> str:
        col = f'"{self.column}"'
        # Konversi operator Unicode ke SQL standar PostgreSQL
        _op_map = {
            "≠": "!=", "≥": ">=", "≤": "<=",
            "NOT BETWEEN": "NOT BETWEEN",
            "NOT LIKE": "NOT LIKE", "NOT ILIKE": "NOT ILIKE",
        }
        op  = _op_map.get(self.operator, self.operator)
        val = self.value.strip()
        if op in ("IS NULL", "IS NOT NULL"):
            return f"{col} {op}"
        if op == "BETWEEN":
            parts = [v.strip() for v in val.split(",")]
            if len(parts) == 2:
                return f"{col} BETWEEN {parts[0]} AND {parts[1]}"
        if op == "NOT BETWEEN":
            parts = [v.strip() for v in val.split(",")]
            if len(parts) == 2:
                return f"{col} NOT BETWEEN {parts[0]} AND {parts[1]}"
        if op in ("IN", "NOT IN"):
            return f"{col} {op} ({val})"
        if op in ("LIKE", "ILIKE", "NOT LIKE", "NOT ILIKE"):
            return f"{col} {op} '{val}'"
        try:
            float(val)
            return f"{col} {op} {val}"
        except ValueError:
            return f"{col} {op} '{val}'"


@dataclass
class QuerySpec:
    schema: str
    table: str
    conditions: List[WhereCondition] = field(default_factory=list)
    select_cols: List[str] = field(default_factory=lambda: ["*"])
    order_col: Optional[str] = None
    order_dir: str = "ASC"
    limit: Optional[int] = None

    def build_sql(self) -> str:
        cols = ", ".join(f'"{c}"' if c != "*" else "*" for c in self.select_cols)
        where = self._build_where()
        parts = [f"SELECT {cols}", f'FROM "{self.schema}"."{self.table}"']
        if where:
            parts.append(where)
        if self.order_col:
            parts.append(f'ORDER BY "{self.order_col}" {self.order_dir}')
        if self.limit:
            parts.append(f"LIMIT {self.limit}")
        return "\n".join(parts)

    def _build_where(self) -> str:
        if not self.conditions:
            return ""
        clauses = []
        for i, cond in enumerate(self.conditions):
            clause = cond.to_sql()
            clauses.append(clause if i == 0 else f"{cond.logic} {clause}")
        return "WHERE " + " ".join(clauses)


@dataclass(frozen=True)
class GeoprocessSpec:
    operation: str
    input_schema: str
    input_table: str
    input_geom: str
    output_table: str
    output_schema: str = "public"
    overlay_schema: Optional[str] = None
    overlay_table: Optional[str] = None
    overlay_geom: Optional[str] = None
    distance: float = 100.0
    tolerance: float = 0.001
    segments: int = 16
    target_srid: int = 4326
    dissolve_field: Optional[str] = None
    value_col: Optional[str] = None
    group_col: Optional[str] = None
    join_left_field: Optional[str] = None   # kolom kunci dari layer input (Join by Field)
    join_right_field: Optional[str] = None  # kolom kunci dari layer/tabel join
    k_neighbors: int = 1
    spatial_predicate: str = "ST_Intersects"
    join_type: str = "INNER"
    area_unit: str = "ha"
    dissolve: bool = False
    preserve_topology: bool = True
