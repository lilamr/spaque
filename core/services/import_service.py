"""
core/services/import_service.py
Orchestrates spatial file → PostGIS import.
"""

from __future__ import annotations

from typing import Optional, Tuple

import geopandas as gpd

from core.database.connection import DatabaseConnection
from core.importers.base import SpatialImporter, ImportSpec, ImportResult, NonSpatialImportResult
from utils.logger import get_logger

logger = get_logger("spaque.services.import")


class ImportService:

    def __init__(self, db_conn: DatabaseConnection):
        self._conn   = db_conn
        self._engine = SpatialImporter(db_conn)

    def preview_file(self, spec: ImportSpec) -> Tuple[Optional[gpd.GeoDataFrame], str]:
        """Return sample rows + info string. Does NOT touch the DB."""
        return self._engine.preview(spec)

    def import_file(self, spec: ImportSpec) -> ImportResult:
        """Full import into PostGIS. Returns ImportResult."""
        logger.info(
            "Starting import: %s → %s.%s",
            spec.file_path.name, spec.target_schema, spec.resolved_table,
        )
        return self._engine.run(spec)

    def get_db_schemas(self) -> list[str]:
        """Return list of schemas from the database."""
        cur = self._conn.cursor()
        try:
            cur.execute("""
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast')
                ORDER BY schema_name
            """)
            return [r[0] for r in cur.fetchall()]
        finally:
            cur.close()

    def table_exists(self, schema: str, table: str) -> bool:
        cur = self._conn.cursor()
        try:
            cur.execute("""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            """, (schema, table))
            return cur.fetchone() is not None
        finally:
            cur.close()

    def import_non_spatial(self, spec: "ImportSpec") -> "NonSpatialImportResult":
        """Import CSV tanpa geometri ke PostgreSQL biasa."""
        logger.info(
            "Non-spatial import: %s → %s.%s",
            spec.file_path.name, spec.target_schema, spec.resolved_table,
        )
        return self._engine.run_non_spatial(spec)
