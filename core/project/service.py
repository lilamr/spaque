"""
core/project/service.py
Mengatur lifecycle project: new, save, save-as, open, recent files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

from core.project.model import (
    ProjectState, DBState, ActiveLayerState,
    WindowState, QueryHistoryEntry, BookmarkEntry,
    SPQ_EXTENSION,
)
from core.project.serializer import ProjectSerializer
from utils.logger import get_logger

logger = get_logger("spaque.project.service")

# ── Recent files storage (simple JSON sidecar) ────────────────────────────────
_RECENT_FILE = Path.home() / ".spaque" / "recent_projects.json"
_MAX_RECENT  = 10


class ProjectService:
    """
    Manages the currently open project and recent-files list.
    Designed to be instantiated once by MainWindow.
    """

    def __init__(self):
        self._state: ProjectState   = ProjectState()   # always has a state
        self._path: Optional[Path]  = None             # None = unsaved new project
        self._dirty: bool           = False            # unsaved changes?
        _ensure_config_dir()

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def state(self) -> ProjectState:
        return self._state

    @property
    def current_path(self) -> Optional[Path]:
        return self._path

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def project_name(self) -> str:
        return self._state.name

    @property
    def window_title(self) -> str:
        name   = self._state.name or "Proyek Tanpa Nama"
        suffix = " *" if self._dirty else ""
        if self._path:
            return f"{name}{suffix} — {self._path.name}"
        return f"{name}{suffix} — [Belum Disimpan]"

    # ── New project ───────────────────────────────────────────────────────────

    def new_project(self, name: str = "Proyek Baru") -> ProjectState:
        self._state = ProjectState(name=name)
        self._path  = None
        self._dirty = False
        logger.info("New project: %s", name)
        return self._state

    # ── Save ──────────────────────────────────────────────────────────────────

    def save(self) -> Tuple[bool, str]:
        """Save to current path. Returns (ok, msg)."""
        if not self._path:
            return False, "Belum ada path — gunakan Save As"
        ok, msg = ProjectSerializer.save(self._state, self._path)
        if ok:
            self._dirty = False
            self._add_recent(self._path)
        return ok, msg

    def save_as(self, path: Path) -> Tuple[bool, str]:
        """Save to a new path."""
        if path.suffix.lower() != SPQ_EXTENSION:
            path = path.with_suffix(SPQ_EXTENSION)
        ok, msg = ProjectSerializer.save(self._state, path)
        if ok:
            self._path  = path
            self._dirty = False
            self._add_recent(path)
        return ok, msg

    # ── Open ──────────────────────────────────────────────────────────────────

    def open(self, path: Path) -> Tuple[Optional[ProjectState], str]:
        """Load .spq file. Returns (state_or_None, message)."""
        state, msg = ProjectSerializer.load(path)
        if state:
            self._state = state
            self._path  = path
            self._dirty = False
            self._add_recent(path)
        return state, msg

    # ── Dirty tracking ────────────────────────────────────────────────────────

    def mark_dirty(self):
        self._dirty = True

    def update_db_state(self, host: str, port: int, dbname: str, user: str,
                        password: str = ""):
        self._state.db = DBState(
            host=host, port=port, dbname=dbname, user=user,
            password_hint=password[:2] + "***" if password else "",
        )
        self.mark_dirty()

    def update_active_layer(self, schema: str, table: str, geom_col: str,
                            sql: str, title: str):
        self._state.active_layer = ActiveLayerState(
            schema=schema, table=table, geom_col=geom_col,
            sql=sql, title=title,
        )
        self.mark_dirty()

    def update_map_state(self, value_col: str = "", colormap: str = "viridis"):
        self._state.map.value_col = value_col
        self._state.map.colormap  = colormap
        self.mark_dirty()

    def update_window_state(self, width: int, height: int, x: int, y: int,
                             maximized: bool,
                             h_split: List[int], v_split: List[int]):
        self._state.window = WindowState(
            width=width, height=height, x=x, y=y,
            maximized=maximized,
            h_split_sizes=h_split,
            v_split_sizes=v_split,
        )
        # Window state changes don't mark dirty (cosmetic)

    def update_sql_console(self, text: str):
        self._state.sql_console.text = text
        self.mark_dirty()

    # ── Query history ─────────────────────────────────────────────────────────

    def add_to_history(self, sql: str, title: str, row_count: int = 0):
        """Add a query to history (dedup by sql, keep latest 50)."""
        # Remove duplicate
        self._state.query_history = [
            h for h in self._state.query_history if h.sql != sql
        ]
        entry = QueryHistoryEntry(sql=sql, title=title, row_count=row_count)
        self._state.query_history.insert(0, entry)
        self._state.query_history = self._state.query_history[:50]
        self.mark_dirty()

    def get_history(self) -> List[QueryHistoryEntry]:
        return self._state.query_history

    def clear_history(self):
        self._state.query_history.clear()
        self.mark_dirty()

    # ── Bookmarks ─────────────────────────────────────────────────────────────

    def add_bookmark(self, name: str, sql: str, description: str = "") -> bool:
        """Add bookmark. Returns False if name already exists."""
        if any(b.name == name for b in self._state.bookmarks):
            return False
        self._state.bookmarks.append(BookmarkEntry(name=name, sql=sql,
                                                    description=description))
        self.mark_dirty()
        return True

    def remove_bookmark(self, name: str):
        self._state.bookmarks = [b for b in self._state.bookmarks if b.name != name]
        self.mark_dirty()

    def get_bookmarks(self) -> List[BookmarkEntry]:
        return self._state.bookmarks

    # ── Recent files ──────────────────────────────────────────────────────────

    def get_recent_files(self) -> List[Path]:
        """Return list of recent .spq paths that still exist."""
        try:
            data = json.loads(_RECENT_FILE.read_text())
            paths = [Path(p) for p in data.get("recent", [])]
            return [p for p in paths if p.exists()]
        except Exception:
            return []

    def _add_recent(self, path: Path):
        recent = self.get_recent_files()
        # Dedup
        recent = [p for p in recent if p != path]
        recent.insert(0, path)
        recent = recent[:_MAX_RECENT]
        try:
            _RECENT_FILE.write_text(
                json.dumps({"recent": [str(p) for p in recent]}, indent=2)
            )
        except Exception:
            pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_config_dir():
    try:
        _RECENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
