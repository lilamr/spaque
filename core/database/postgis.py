"""
core/database/postgis.py — PostGIS metadata and spatial queries
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import geopandas as gpd

from core.database.connection import DatabaseConnection
from core.domain.entities.layer import LayerInfo, LayerColumn
from utils.logger import get_logger

logger = get_logger("spaque.db.postgis")


class PostGISDatabase:
    """
    Encapsulates all PostGIS-specific interactions:
    layer discovery, metadata, spatial data fetching.
    """

    def __init__(self, conn: DatabaseConnection):
        self._conn = conn

    # ── Layer discovery ───────────────────────────────────────────────────────

    def list_spatial_layers(self) -> List[LayerInfo]:
        """Return all spatial tables from geometry_columns view."""
        sql = """
            SELECT
                gc.f_table_schema   AS schema,
                gc.f_table_name     AS table_name,
                gc.f_geometry_column AS geom_col,
                gc.type             AS geom_type,
                gc.srid,
                col_count
            FROM geometry_columns gc
            JOIN (
                SELECT table_schema, table_name, COUNT(*) AS col_count
                FROM information_schema.columns
                GROUP BY table_schema, table_name
            ) cnt ON cnt.table_schema = gc.f_table_schema
                 AND cnt.table_name = gc.f_table_name
            ORDER BY gc.f_table_schema, gc.f_table_name
        """
        cur = self._conn.cursor(dict_cursor=True)
        try:
            cur.execute(sql)
            rows = cur.fetchall()
        finally:
            cur.close()

        return [
            LayerInfo(
                schema=r["schema"],
                table_name=r["table_name"],
                geom_col=r["geom_col"],
                geom_type=r["geom_type"],
                srid=r["srid"],
                col_count=r["col_count"],
            )
            for r in rows
        ]

    def list_all_tables(self, schemas: Optional[List[str]] = None) -> List[LayerInfo]:
        """
        Return all user tables including non-spatial tables.
        Spatial tables include geometry metadata; non-spatial tables have empty geom_col/geom_type.
        """
        schema_filter = ""
        params: List = []
        if schemas:
            placeholders = ",".join(["%s"] * len(schemas))
            schema_filter = f"AND table_schema IN ({placeholders})"
            params = schemas

        sql = f"""
            SELECT
                c.table_schema AS schema,
                c.table_name,
                (
                    SELECT COUNT(*)
                    FROM information_schema.columns c2
                    WHERE c2.table_schema = c.table_schema
                      AND c2.table_name   = c.table_name
                ) AS col_count
            FROM information_schema.tables t
            JOIN information_schema.columns c
              ON c.table_schema = t.table_schema
              AND c.table_name   = t.table_name
            WHERE t.table_type = 'BASE TABLE'
              AND t.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'topology')
              {schema_filter}
            GROUP BY c.table_schema, c.table_name, t.table_type
            ORDER BY c.table_schema, c.table_name
        """
        cur = self._conn.cursor(dict_cursor=True)
        try:
            cur.execute(sql, params)
            rows = cur.fetchall()
        finally:
            cur.close()

        spatial_layers = {r.qualified_name: r for r in self.list_spatial_layers()}

        result: List[LayerInfo] = []
        for r in rows:
            qname = f'"{r["schema"]}"."{r["table_name"]}"'
            if qname in spatial_layers:
                result.append(spatial_layers[qname])
            else:
                result.append(LayerInfo(
                    schema=r["schema"],
                    table_name=r["table_name"],
                    geom_col="",
                    geom_type="",
                    srid=0,
                    col_count=r["col_count"],
                ))
        return result

    def get_layer_columns(self, layer: LayerInfo) -> List[LayerColumn]:
        sql = """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        cur = self._conn.cursor(dict_cursor=True)
        try:
            cur.execute(sql, (layer.schema, layer.table_name))
            rows = cur.fetchall()
        finally:
            cur.close()
        return [LayerColumn(r["column_name"], r["data_type"], r["udt_name"])
                for r in rows]

    def get_row_count(self, layer: LayerInfo) -> int:
        import psycopg2.sql as sql
        cur = self._conn.cursor()
        try:
            query = sql.SQL("SELECT COUNT(*) FROM {}").format(
                sql.Identifier(layer.schema, layer.table_name)
            )
            cur.execute(query)
            return cur.fetchone()[0]
        finally:
            cur.close()

    def get_schemas(self) -> List[str]:
        cur = self._conn.cursor()
        try:
            cur.execute("""
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name NOT IN
                    ('pg_catalog','information_schema','pg_toast')
                ORDER BY schema_name
            """)
            return [r[0] for r in cur.fetchall()]
        finally:
            cur.close()

    # ── Data fetching ─────────────────────────────────────────────────────────

    def fetch_geodataframe(self, sql: str,
                           geom_col: Optional[str] = None) -> Optional[gpd.GeoDataFrame]:
        """
        Execute spatial SQL and return a GeoDataFrame.
        Auto-detects geometry column when geom_col is None.
        """
        try:
            engine = self._conn.sqlalchemy_engine()
            if geom_col:
                gdf = gpd.read_postgis(sql, engine, geom_col=geom_col)
            else:
                gdf = gpd.read_postgis(sql, engine)
            logger.debug("Fetched GDF: %d rows, cols=%s", len(gdf), list(gdf.columns))
            return gdf
        except Exception as exc:
            logger.warning("GeoDataFrame fetch failed: %s", exc)
            return None

    def fetch_raw(self, sql: str) -> Tuple[List[str], List[tuple]]:
        """Execute validated SQL and return (column_names, rows)."""
        self._conn.ensure_connection()
        cur = self._conn.cursor()
        try:
            cur.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return cols, rows
        finally:
            cur.close()

    def fetch_raw_safe(self, sql: str, params: tuple = ()) -> Tuple[List[str], List[tuple]]:
        """Execute parameterized SQL and return (column_names, rows)."""
        self._conn.ensure_connection()
        cur = self._conn.cursor()
        try:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return cols, rows
        finally:
            cur.close()

    # ── Write operations ──────────────────────────────────────────────────────

    def _make_write_connection(self):
        """
        Buat koneksi psycopg2 baru khusus untuk operasi tulis (DDL).
        Ini memastikan thread-safety: tidak berbagi koneksi dengan main thread.
        """
        import psycopg2 as _psycopg2
        p = self._conn.params   # property, bukan attribute private
        if not p:
            raise RuntimeError("Not connected to database")
        conn = _psycopg2.connect(
            host=p.host, port=p.port, dbname=p.dbname,
            user=p.user, password=p.password, connect_timeout=30,
        )
        conn.autocommit = False
        return conn

    def create_table_from_sql(self, sql: str,
                              schema: str, table: str) -> Tuple[bool, str, int]:
        """
        DROP IF EXISTS + CREATE TABLE AS (sql).
        Jika hasil punya kolom geometri ganda (geom + geom_clipped, dll.),
        kolom geometri asli di-DROP dan kolom hasil di-RENAME ke 'geom'
        agar tabel hanya punya satu kolom geometri aktif.
        Returns (success, message, row_count).

        Thread-safe: membuat koneksi psycopg2 sendiri per panggilan,
        tidak memakai shared connection dari main thread.
        """
        target = f'"{schema}"."{table}"'
        try:
            write_conn = self._make_write_connection()
        except Exception as exc:
            logger.error("create_table_from_sql: gagal buat koneksi write: %s", exc)
            return False, f"Gagal koneksi ke database: {exc}", 0

        cur = write_conn.cursor()
        try:
            cur.execute(f"DROP TABLE IF EXISTS {target}")
            cur.execute(f"CREATE TABLE {target} AS ({sql})")

            # ── Normalisasi kolom geometri ──────────────────────────────────
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                  AND udt_name = 'geometry'
                ORDER BY ordinal_position
            """, (schema, table))
            geom_cols = [r[0] for r in cur.fetchall()]

            if len(geom_cols) > 1:
                result_geom   = next((c for c in geom_cols if c != 'geom'), geom_cols[-1])
                original_geom = next((c for c in geom_cols if c != result_geom), geom_cols[0])
                cur.execute(f'ALTER TABLE {target} DROP COLUMN IF EXISTS "{original_geom}"')
                if result_geom != 'geom':
                    cur.execute(f'ALTER TABLE {target} RENAME COLUMN "{result_geom}" TO "geom"')
                logger.debug("Geom columns normalized: dropped '%s', renamed '%s' → 'geom'",
                             original_geom, result_geom)

            cur.execute(
                f'ALTER TABLE {target} ADD COLUMN IF NOT EXISTS _gid SERIAL PRIMARY KEY')

            cur.execute(f"SELECT COUNT(*) FROM {target}")
            count = cur.fetchone()[0]
            write_conn.commit()
            msg = f"Tabel '{table}' berhasil dibuat dengan {count:,} fitur"
            logger.info(msg)
            return True, msg, count
        except Exception as exc:
            try:
                write_conn.rollback()
            except Exception:
                pass
            logger.error("create_table_from_sql failed: %s", exc)
            return False, str(exc), 0
        finally:
            cur.close()
            try:
                write_conn.close()
            except Exception:
                pass
