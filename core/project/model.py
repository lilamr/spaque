"""
core/project/model.py
Dataclasses yang merepresentasikan seluruh state project Spaque (.spq).

File .spq adalah JSON terenkripsi (base64 gzip) dengan struktur:
{
  "spaque_version": "1.0",
  "project": { ... ProjectState ... }
}
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List
from datetime import datetime


SPAQUE_VERSION   = "1.0"
SPQ_EXTENSION    = ".spq"
SPQ_MAGIC        = "SPAQUE_PROJECT"   # first key in JSON untuk validasi


# ── Sub-state pieces ──────────────────────────────────────────────────────────

@dataclass
class DBState:
    """Koneksi database terakhir."""
    host: str = "localhost"
    port: int = 5432
    dbname: str = ""
    user: str = "postgres"
    # Password TIDAK disimpan — user diminta masukkan ulang saat buka project
    save_password: bool = False
    password_hint: str = ""   # hanya 2 karakter pertama + "***" sebagai hint


@dataclass
class ActiveLayerState:
    """Layer yang sedang aktif di peta."""
    schema: str = ""
    table: str = ""
    geom_col: str = ""
    sql: str = ""               # SQL query yang menghasilkan data ini
    title: str = ""
    value_col: str = ""         # kolom choropleth
    colormap: str = "viridis"


@dataclass
class QueryHistoryEntry:
    """Satu entri riwayat query SQL."""
    sql: str
    title: str
    timestamp: str = ""
    row_count: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat(timespec="seconds")


@dataclass
class BookmarkEntry:
    """Query yang di-bookmark oleh user."""
    name: str
    sql: str
    description: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat(timespec="seconds")


@dataclass
class WindowState:
    """Ukuran dan posisi jendela, splitter, dll."""
    width: int = 1440
    height: int = 880
    x: int = -1
    y: int = -1
    maximized: bool = False
    h_split_sizes: List[int] = field(default_factory=lambda: [270, 1140])
    v_split_sizes: List[int] = field(default_factory=lambda: [580, 260])


@dataclass
class MapState:
    """State peta terakhir."""
    center_lat: float = 0.0
    center_lon: float = 0.0
    zoom: int = 10
    basemap: str = "CartoDB dark_matter"
    colormap: str = "viridis"
    value_col: str = ""


@dataclass
class SQLConsoleState:
    """Isi SQL console terakhir."""
    text: str = ""


# ── Root project state ────────────────────────────────────────────────────────

@dataclass
class ProjectState:
    """
    Root object — semua state Spaque ada di sini.
    Serialized as JSON inside .spq file.
    """
    # Meta
    name: str = "Proyek Tanpa Nama"
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    spaque_version: str = SPAQUE_VERSION

    # State
    db: DBState = field(default_factory=DBState)
    active_layer: ActiveLayerState = field(default_factory=ActiveLayerState)
    window: WindowState = field(default_factory=WindowState)
    map: MapState = field(default_factory=MapState)
    sql_console: SQLConsoleState = field(default_factory=SQLConsoleState)

    # History & bookmarks
    query_history: List[QueryHistoryEntry] = field(default_factory=list)
    bookmarks: List[BookmarkEntry] = field(default_factory=list)

    # Arbitrary extras (forward compatibility)
    extras: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        now = datetime.now().isoformat(timespec="seconds")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def touch(self):
        """Update updated_at timestamp."""
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    # ── Serialization helpers ─────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectState":
        """Reconstruct from dict, tolerating missing keys (forward compat)."""
        db_data   = data.pop("db", {})
        lay_data  = data.pop("active_layer", {})
        win_data  = data.pop("window", {})
        map_data  = data.pop("map", {})
        sql_data  = data.pop("sql_console", {})
        hist_data = data.pop("query_history", [])
        bkmk_data = data.pop("bookmarks", [])

        state = cls(
            db=DBState(**{k: v for k, v in db_data.items()
                          if k in DBState.__dataclass_fields__}),
            active_layer=ActiveLayerState(**{k: v for k, v in lay_data.items()
                                             if k in ActiveLayerState.__dataclass_fields__}),
            window=WindowState(**{k: v for k, v in win_data.items()
                                  if k in WindowState.__dataclass_fields__}),
            map=MapState(**{k: v for k, v in map_data.items()
                            if k in MapState.__dataclass_fields__}),
            sql_console=SQLConsoleState(**{k: v for k, v in sql_data.items()
                                           if k in SQLConsoleState.__dataclass_fields__}),
            query_history=[QueryHistoryEntry(**{k: v for k, v in h.items()
                                                if k in QueryHistoryEntry.__dataclass_fields__})
                           for h in hist_data],
            bookmarks=[BookmarkEntry(**{k: v for k, v in b.items()
                                        if k in BookmarkEntry.__dataclass_fields__})
                       for b in bkmk_data],
            **{k: v for k, v in data.items() if k in cls.__dataclass_fields__
               and k not in ("db","active_layer","window","map","sql_console",
                              "query_history","bookmarks")},
        )
        return state
