"""
core/database/connection.py — PostgreSQL/PostGIS connection pool
"""

from __future__ import annotations

import threading
from typing import Optional, Tuple

import psycopg2
import psycopg2.extras
import psycopg2.pool

from config import DatabaseConfig
from core.domain.value_objects import ConnectionParams
from utils.logger import get_logger

logger = get_logger("spaque.db.connection")


class DatabaseConnection:
    """
    Thread-safe singleton-like connection manager.
    Wraps a psycopg2 simple connection (one user, desktop app).
    """

    _lock = threading.Lock()

    def __init__(self):
        self._conn: Optional[psycopg2.extensions.connection] = None
        self._params: Optional[ConnectionParams] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def connect(self, params: ConnectionParams) -> Tuple[bool, str]:
        """
        Establish connection. Returns (success, message).
        """
        with self._lock:
            try:
                if self._conn:
                    try:
                        self._conn.close()
                    except Exception:
                        pass

                self._conn = psycopg2.connect(
                    host=params.host,
                    port=params.port,
                    dbname=params.dbname,
                    user=params.user,
                    password=params.password,
                    connect_timeout=8,
                )
                self._conn.autocommit = False

                # Verify PostGIS
                version = self._query_scalar("SELECT PostGIS_Version()")
                postgis_ver = version.split()[0] if version else "?"
                self._params = params
                logger.info("Connected to %s | PostGIS %s", params.safe_label, postgis_ver)
                return True, f"PostGIS {postgis_ver}"

            except psycopg2.OperationalError as exc:
                self._conn = None
                logger.error("Connection failed: %s", exc)
                return False, str(exc)
            except Exception as exc:
                self._conn = None
                logger.error("PostGIS check failed: %s", exc)
                return False, f"PostGIS tidak terdeteksi: {exc}"

    def disconnect(self):
        with self._lock:
            if self._conn:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
                self._params = None
                logger.info("Disconnected")

    @property
    def is_connected(self) -> bool:
        if self._conn is None:
            return False
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return True
        except Exception:
            return False

    @property
    def params(self) -> Optional[ConnectionParams]:
        return self._params

    def cursor(self, dict_cursor: bool = False):
        """Return a cursor. Raises if not connected."""
        if not self.is_connected:
            raise RuntimeError("Not connected to database")
        factory = psycopg2.extras.RealDictCursor if dict_cursor else None
        return self._conn.cursor(cursor_factory=factory)

    def commit(self):
        if self._conn:
            self._conn.commit()

    def rollback(self):
        if self._conn:
            self._conn.rollback()

    def sqlalchemy_engine(self):
        """SQLAlchemy engine for geopandas.read_postgis."""
        from sqlalchemy import create_engine
        p = self._params
        if not p:
            raise RuntimeError("Not connected")
        url = (f"postgresql+psycopg2://{p.user}:{p.password}"
               f"@{p.host}:{p.port}/{p.dbname}")
        return create_engine(url, pool_pre_ping=True)

    # ── Private ───────────────────────────────────────────────────────────────

    def _query_scalar(self, sql: str):
        cur = self._conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None
