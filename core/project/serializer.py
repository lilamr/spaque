"""
core/project/serializer.py
Baca & tulis file .spq (JSON + gzip + base64 header).

Format file .spq:
  Byte 0-12 : b"SPAQUE_PRJ_1"  (magic + version identifier, 12 bytes)
  Byte 12+  : gzip( utf-8 JSON payload )

Kenapa gzip? — file shapefile & query histories bisa panjang; gzip juga
mencegah user iseng edit manual dan menjaga integritas.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Tuple

from core.project.model import ProjectState, SPQ_MAGIC, SPAQUE_VERSION
from utils.logger import get_logger

logger = get_logger("spaque.project.serializer")

# ── Constants ─────────────────────────────────────────────────────────────────

_MAGIC_BYTES = b"SPAQUE_PRJ_1"   # 12-byte magic header
_MAX_FILE_MB = 50                  # sanity guard


class ProjectSerializer:
    """Read / write .spq files."""

    # ── Write ─────────────────────────────────────────────────────────────────

    @staticmethod
    def save(state: ProjectState, path: Path) -> Tuple[bool, str]:
        """
        Serialize ProjectState → .spq file.
        Returns (success, message).
        """
        try:
            state.touch()
            payload = {
                SPQ_MAGIC: True,
                "spaque_version": SPAQUE_VERSION,
                "project": state.to_dict(),
            }
            json_bytes = json.dumps(
                payload,
                ensure_ascii=False,
                indent=None,              # compact
                default=str,
            ).encode("utf-8")

            compressed = gzip.compress(json_bytes, compresslevel=6)

            path.write_bytes(_MAGIC_BYTES + compressed)

            size_kb = path.stat().st_size / 1024
            logger.info("Project saved: %s  (%.1f KB)", path.name, size_kb)
            return True, f"Project disimpan: {path.name}  ({size_kb:.1f} KB)"

        except Exception as exc:
            logger.error("Save failed: %s", exc)
            return False, f"Gagal menyimpan project: {exc}"

    # ── Read ──────────────────────────────────────────────────────────────────

    @staticmethod
    def load(path: Path) -> Tuple[ProjectState | None, str]:
        """
        Deserialize .spq file → ProjectState.
        Returns (state_or_None, message).
        """
        try:
            if not path.exists():
                return None, f"File tidak ditemukan: {path}"

            size_mb = path.stat().st_size / 1_048_576
            if size_mb > _MAX_FILE_MB:
                return None, f"File terlalu besar ({size_mb:.1f} MB > {_MAX_FILE_MB} MB)"

            raw = path.read_bytes()

            # Validate magic header
            if not raw.startswith(_MAGIC_BYTES):
                return None, (
                    "File bukan project Spaque yang valid.\n"
                    "Pastikan file berekstensi .spq dan dibuat oleh Spaque."
                )

            # Decompress
            compressed = raw[len(_MAGIC_BYTES):]
            try:
                json_bytes = gzip.decompress(compressed)
            except gzip.BadGzipFile:
                return None, "File project rusak (kompresi tidak valid)"

            # Parse JSON
            payload = json.loads(json_bytes.decode("utf-8"))

            # Validate magic key
            if not payload.get(SPQ_MAGIC):
                return None, "Format file project tidak dikenali"

            # Reconstruct state
            project_dict = payload.get("project", {})
            state = ProjectState.from_dict(project_dict)

            logger.info(
                "Project loaded: %s  (v%s, updated %s)",
                path.name, payload.get("spaque_version", "?"), state.updated_at
            )
            return state, f"Project dibuka: {path.name}"

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error: %s", exc)
            return None, f"File project tidak bisa dibaca (JSON error): {exc}"
        except Exception as exc:
            logger.error("Load failed: %s", exc)
            return None, f"Gagal membuka project: {exc}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def is_spq_file(path: Path) -> bool:
        """Quick check without full parse."""
        try:
            if path.suffix.lower() != ".spq":
                return False
            raw = path.read_bytes(12)
            return raw == _MAGIC_BYTES
        except Exception:
            return False

    @staticmethod
    def peek_metadata(path: Path) -> dict:
        """
        Read only name/description/updated_at without full deserialise.
        Returns {} on failure.
        """
        try:
            state, msg = ProjectSerializer.load(path)
            if state:
                return {
                    "name": state.name,
                    "description": state.description,
                    "created_at": state.created_at,
                    "updated_at": state.updated_at,
                    "db_host": state.db.host,
                    "db_name": state.db.dbname,
                }
        except Exception:
            pass
        return {}
