"""
utils/helpers.py — General-purpose utility functions
"""

from __future__ import annotations

import re
from typing import Any, List, Optional


def slugify(text: str, max_len: int = 50) -> str:
    """Convert text to a safe SQL identifier."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text[:max_len].strip("_")


def safe_sql_identifier(schema: str, table: str) -> str:
    return f'"{schema}"."{table}"'


def format_number(n: float, decimals: int = 2) -> str:
    if n is None:
        return "—"
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.{decimals}f} jt"
    if abs(n) >= 1_000:
        return f"{n/1_000:.{decimals}f} rb"
    return f"{n:.{decimals}f}"


def truncate_str(s: str, max_len: int = 60) -> str:
    if s is None:
        return ""
    s = str(s)
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def detect_geom_col(columns: List[dict]) -> Optional[str]:
    """Detect geometry column from column info list."""
    for c in columns:
        if c.get("udt_name") == "geometry":
            return c["column_name"]
    for c in columns:
        if c["column_name"].lower() in ("geom", "geometry", "the_geom", "wkb_geometry"):
            return c["column_name"]
    return None


def is_numeric_type(pg_type: str) -> bool:
    from utils.constants import NUMERIC_TYPES
    return pg_type.lower() in NUMERIC_TYPES


def parse_int_safe(value: str, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def build_connection_label(host: str, user: str, dbname: str) -> str:
    return f"{user}@{host}/{dbname}"
