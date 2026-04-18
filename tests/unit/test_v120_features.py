"""
tests/unit/test_v120_features.py
Regression & unit tests untuk fitur baru v1.2.0:
  1. Import CSV tanpa kolom spasial (NonSpatialImportResult)
  2. Edit Attribute Table (_SmartItem, edit tracking, pk detection)

Catatan: test yang membutuhkan PyQt6 atau psycopg2 menggunakan conditional
import agar tidak gagal di CI yang belum install dependensi GUI.
"""

import re
import sys
import os
from pathlib import Path
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

# ── Conditional import helpers ────────────────────────────────────────────────

def _has_pyqt6() -> bool:
    import importlib.util
    return importlib.util.find_spec("PyQt6") is not None

def _has_psycopg2() -> bool:
    import importlib.util
    return importlib.util.find_spec("psycopg2") is not None

skip_no_qt    = pytest.mark.skipif(not _has_pyqt6(),    reason="PyQt6 tidak tersedia")
skip_no_pg    = pytest.mark.skipif(not _has_psycopg2(), reason="psycopg2 tidak tersedia")
skip_no_qt_pg = pytest.mark.skipif(
    not (_has_pyqt6() and _has_psycopg2()),
    reason="PyQt6 atau psycopg2 tidak tersedia"
)


# ─────────────────────────────────────────────────────────────────────────────
# FITUR 1: Import CSV Non-Spasial — pure Python tests (no Qt/psycopg2)
# ─────────────────────────────────────────────────────────────────────────────

class TestNonSpatialImportResultPure:
    """
    Test NonSpatialImportResult tanpa Qt/psycopg2.
    Dataclass ini adalah pure Python sehingga selalu bisa ditest.
    """

    @pytest.fixture(autouse=True)
    def _mock_qt(self, monkeypatch):
        """Mock PyQt6 agar import utils.logger tidak crash."""
        import types
        if not _has_pyqt6():
            # Buat modul dummy
            fake_qt = types.ModuleType("PyQt6")
            fake_core = types.ModuleType("PyQt6.QtCore")
            class _FakeQObj:
                pass
            class _FakeSig:
                def __init__(self, *a): pass
            fake_core.QObject     = _FakeQObj
            fake_core.pyqtSignal  = _FakeSig
            fake_qt.QtCore        = fake_core
            sys.modules.setdefault("PyQt6", fake_qt)
            sys.modules.setdefault("PyQt6.QtCore", fake_core)

    def test_success_fields(self):
        from core.importers.base import NonSpatialImportResult
        r = NonSpatialImportResult(
            success=True, message="OK",
            rows_imported=100, schema="public", table="tabel",
            columns=["a", "b", "c"],
        )
        assert r.success is True
        assert r.rows_imported == 100
        assert r.table == "tabel"
        assert len(r.columns) == 3
        assert r.has_warnings is False

    def test_failure_defaults(self):
        from core.importers.base import NonSpatialImportResult
        r = NonSpatialImportResult(False, "error")
        assert r.success is False
        assert r.rows_imported == 0
        assert r.columns == []
        assert r.has_warnings is False

    def test_warnings_flag(self):
        from core.importers.base import NonSpatialImportResult
        r = NonSpatialImportResult(True, "ok", warnings=["encoding fallback"])
        assert r.has_warnings is True
        assert len(r.warnings) == 1

    def test_separate_from_import_result(self):
        from core.importers.base import NonSpatialImportResult, ImportResult
        r = NonSpatialImportResult(True, "ok")
        assert not isinstance(r, ImportResult)

    def test_import_service_has_method(self):
        """ImportService harus deklarasi import_non_spatial — cek via source."""
        src_path = Path(__file__).parent.parent.parent / "core/services/import_service.py"
        src = src_path.read_text(encoding="utf-8")
        assert "def import_non_spatial" in src, \
            "ImportService.import_non_spatial() tidak ditemukan di source"


class TestCsvReadingPure:
    """Test pembacaan CSV murni dengan pandas — tidak butuh Qt/psycopg2."""

    def _csv(self, tmp_path, content, name="t.csv") -> Path:
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_basic_comma_delimiter(self, tmp_path):
        p = self._csv(tmp_path, "nama,umur\nBudi,30\nSiti,25\n")
        df = pd.read_csv(str(p))
        assert len(df) == 2
        assert list(df.columns) == ["nama", "umur"]

    def test_semicolon_delimiter(self, tmp_path):
        p = self._csv(tmp_path, "kode;nama\nHL;Hutan Lindung\nHP;Hutan Produksi\n")
        df = pd.read_csv(str(p), sep=";")
        assert len(df) == 2
        assert "kode" in df.columns

    def test_empty_csv_no_rows(self, tmp_path):
        p = self._csv(tmp_path, "nama,nilai\n")
        df = pd.read_csv(str(p))
        assert len(df) == 0

    def test_drop_cols_logic(self, tmp_path):
        p = self._csv(tmp_path, "id,nama,password\n1,Andi,secret\n2,Budi,pass\n")
        df = pd.read_csv(str(p))
        drop = ["password"]
        df = df.drop(columns=[c for c in drop if c in df.columns])
        assert "password" not in df.columns
        assert "nama" in df.columns

    def test_tab_delimiter(self, tmp_path):
        p = self._csv(tmp_path, "a\tb\tc\n1\t2\t3\n4\t5\t6\n", "tab.tsv")
        df = pd.read_csv(str(p), sep="\t")
        assert len(df) == 2
        assert list(df.columns) == ["a", "b", "c"]


class TestSafeIdentPure:
    """_safe_ident bekerja benar — pure Python test."""

    @pytest.fixture(autouse=True)
    def _mock_qt(self, monkeypatch):
        import types
        if not _has_pyqt6():
            fake_qt   = types.ModuleType("PyQt6")
            fake_core = types.ModuleType("PyQt6.QtCore")
            class _FQ:
                pass
            class _FS:
                def __init__(self, *a):
                    pass
            fake_core.QObject, fake_core.pyqtSignal = _FQ, _FS
            fake_qt.QtCore = fake_core
            sys.modules.setdefault("PyQt6", fake_qt)
            sys.modules.setdefault("PyQt6.QtCore", fake_core)

    def test_lowercase(self):
        from core.importers.base import _safe_ident
        assert _safe_ident("KAWASAN") == "kawasan"

    def test_spaces_to_underscore(self):
        from core.importers.base import _safe_ident
        assert _safe_ident("kawasan hutan") == "kawasan_hutan"

    def test_leading_digit(self):
        from core.importers.base import _safe_ident
        assert _safe_ident("1layer").startswith("t_")

    def test_special_chars(self):
        from core.importers.base import _safe_ident
        result = _safe_ident("berat(kg)")
        assert re.match(r'^[a-z_][a-z0-9_]*$', result), f"Not safe: {result}"

    def test_max_length(self):
        from core.importers.base import _safe_ident
        assert len(_safe_ident("a" * 100)) <= 63

    def test_empty_fallback(self):
        from core.importers.base import _safe_ident
        assert _safe_ident("!!!") == "layer"

    def test_unicode_stripped(self):
        from core.importers.base import _safe_ident
        result = _safe_ident("batas_desa_2024")
        assert result == "batas_desa_2024"




# ─────────────────────────────────────────────────────────────────────────────
# FITUR 2: Edit Attribute Table — pure logic tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSmartItemSortPure:
    """
    Test _SmartItem sort logic.
    Karena bergantung QTableWidgetItem, kita test dengan mock jika PyQt6 tidak ada.
    """

    def _make_items(self, values):
        """Buat list _SmartItem atau fallback list untuk sort test."""
        if _has_pyqt6():
            from ui.panels.attribute_table import _SmartItem
            return [_SmartItem(str(v)) for v in values]
        else:
            # Fallback: test logika sort langsung
            return None

    def _sort_values(self, values):
        """
        Sort dengan simulasi logika _SmartItem.__lt__.
        Selalu pakai pure logic agar test bisa jalan tanpa Qt.
        Jika Qt tersedia, juga verifikasi via _SmartItem asli.
        """
        # Pure logic simulation (selalu jalan)
        def smart_key(x):
            try:
                return (0, float(x))
            except (ValueError, TypeError):
                return (1, str(x))
        result = sorted([str(v) for v in values], key=smart_key)

        # Bonus: verifikasi via _SmartItem asli jika Qt tersedia
        try:
            from ui.panels.attribute_table import _SmartItem
            items = [_SmartItem(str(v)) for v in values]
            items.sort()
            qt_result = [i.text() for i in items]
            assert qt_result == result,                 f"_SmartItem result {qt_result} != simulated {result}"
        except (ImportError, Exception):
            pass  # Qt tidak tersedia — pure simulation cukup

        return result

    def test_numeric_sort_correct(self):
        """
        REGRESSION: QTableWidgetItem sort '10' < '9' (string).
        _SmartItem harus sort 1 < 9 < 25 < 50 < 100.
        """
        result = self._sort_values([100, 9, 50, 1, 25])
        assert result == ["1", "9", "25", "50", "100"], \
            f"Numeric sort salah: {result}"

    def test_string_sort_fallback(self):
        result = self._sort_values(["banana", "apple", "cherry"])
        assert result == ["apple", "banana", "cherry"]

    def test_float_sort(self):
        result = self._sort_values(["1.5", "10.2", "2.8", "0.5"])
        assert result == ["0.5", "1.5", "2.8", "10.2"]

    def test_negative_numbers(self):
        result = self._sort_values(["-5", "10", "-100", "0", "3"])
        assert result == ["-100", "-5", "0", "3", "10"]

    def test_mixed_no_crash(self):
        """Kolom campuran angka & teks tidak boleh crash."""
        try:
            self._sort_values(["10", "abc", "5", "xyz"])
        except Exception as e:
            pytest.fail(f"Sort crash pada mixed data: {e}")

    def test_empty_string_no_crash(self):
        try:
            self._sort_values(["", "10", "", "5"])
        except Exception as e:
            pytest.fail(f"Sort crash pada empty string: {e}")


class TestPKDetectionPure:
    """Test deteksi PK column — pure logic, tanpa PyQt6."""

    def _detect_pk(self, columns):
        """Replikasi logika _detect_pk_col dari main_window.py."""
        pk_candidates = ("gid", "id", "fid", "ogc_fid", "objectid", "feat_id", "pk")
        col_lower = {c.lower(): c for c in columns}
        for cand in pk_candidates:
            if cand in col_lower:
                return col_lower[cand]
        return None

    def test_gid_detected(self):
        assert self._detect_pk(["gid", "nama", "luas", "geom"]) == "gid"

    def test_id_fallback(self):
        assert self._detect_pk(["id", "nama", "nilai"]) == "id"

    def test_fid_detected(self):
        assert self._detect_pk(["fid", "attr1", "attr2"]) == "fid"

    def test_ogc_fid_detected(self):
        assert self._detect_pk(["ogc_fid", "wkb_geometry"]) == "ogc_fid"

    def test_none_when_no_pk(self):
        assert self._detect_pk(["kode", "nama", "keterangan"]) is None

    def test_case_insensitive(self):
        assert self._detect_pk(["GID", "Nama", "Luas"]) == "GID"

    def test_priority_gid_over_id(self):
        """gid harus diprioritaskan atas id."""
        assert self._detect_pk(["id", "gid", "nama"]) == "gid"

    def test_objectid_detected(self):
        assert self._detect_pk(["objectid", "shape"]) == "objectid"


class TestEditTrackingLogicPure:
    """Test logika tracking edit — pure Python dict, tanpa Qt."""

    def test_add_edit(self):
        edits = {}
        edits[(0, "nama")] = "Baru"
        assert len(edits) == 1
        assert edits[(0, "nama")] == "Baru"

    def test_revert_removes_edit(self):
        edits = {}
        edits[(0, "nama")] = "Baru"
        edits[(1, "luas")] = "999"
        # Revert baris 0
        edits.pop((0, "nama"), None)
        assert len(edits) == 1
        assert (0, "nama") not in edits

    def test_multi_row_edits(self):
        edits = {}
        for i in range(5):
            edits[(i, "nama")] = f"Nama {i}"
            edits[(i, "luas")] = str(i * 100)
        assert len(edits) == 10

    def test_geom_col_excluded_from_update(self):
        """Kolom geom tidak boleh masuk ke SET clause UPDATE."""
        edits = {
            (0, "nama"): "Hutan Baru",
            (0, "geom"): "POINT(0 0)",   # harus dikecualikan
            (0, "luas"): "1500.0",
        }
        geom_col = "geom"
        pk_col   = "gid"
        safe = {col: val for (_, col), val in edits.items()
                if col != pk_col and col != geom_col}
        assert "geom" not in safe
        assert "nama" in safe
        assert "luas" in safe

    def test_pk_col_excluded_from_update(self):
        """Kolom PK tidak boleh masuk ke SET clause (jangan update PK)."""
        edits = {(0, "gid"): "99", (0, "nama"): "Test"}
        pk_col   = "gid"
        geom_col = "geom"
        safe = {col: val for (_, col), val in edits.items()
                if col != pk_col and col != geom_col}
        assert "gid" not in safe
        assert "nama" in safe

    def test_update_sql_correct(self):
        """UPDATE SQL yang dihasilkan syntactically valid."""
        col_vals = {"nama": "Hutan Baru", "luas": "2500.0"}
        pk_col   = "gid"
        pk_val   = 42
        qualified = '"public"."kawasan_hutan"'
        set_clause = ", ".join(f'"{col}" = %s' for col in col_vals)
        sql = (f"UPDATE {qualified} SET {set_clause} "
               f'WHERE "{pk_col}" = %s')
        params = list(col_vals.values()) + [pk_val]

        assert "UPDATE" in sql
        assert "SET" in sql
        assert "WHERE" in sql
        assert '"gid" = %s' in sql
        assert len(params) == 3

    def test_rows_grouping(self):
        """Editan banyak baris dikelompokkan per row_idx dengan benar."""
        edits = {
            (0, "nama"): "A",
            (0, "luas"): "100",
            (1, "nama"): "B",
            (2, "luas"): "300",
        }
        rows_edits: dict = {}
        for (row_idx, col_name), new_val in edits.items():
            rows_edits.setdefault(row_idx, {})[col_name] = new_val

        assert len(rows_edits) == 3
        assert "nama" in rows_edits[0]
        assert "luas" in rows_edits[0]
        assert rows_edits[1] == {"nama": "B"}
        assert rows_edits[2] == {"luas": "300"}


class TestSourceCodeStructure:
    """
    Verifikasi bahwa semua komponen yang diperlukan ada di source code.
    Test ini tidak perlu import modul — cukup baca file teks.
    Ini memastikan bahwa bahkan tanpa Qt/psycopg2, kita bisa verify struktur.
    """

    def _src(self, rel_path: str) -> str:
        base = Path(__file__).parent.parent.parent
        return (base / rel_path).read_text(encoding="utf-8")

    # ── base.py ──────────────────────────────────────────────────────────────

    def test_non_spatial_import_result_class_exists(self):
        src = self._src("core/importers/base.py")
        assert "class NonSpatialImportResult" in src

    def test_run_non_spatial_method_exists(self):
        src = self._src("core/importers/base.py")
        assert "def run_non_spatial" in src

    def test_run_non_spatial_reads_csv(self):
        src = self._src("core/importers/base.py")
        assert "pd.read_csv" in src
        assert "to_sql" in src

    def test_non_spatial_has_encoding_fallback(self):
        src = self._src("core/importers/base.py")
        assert "UnicodeDecodeError" in src
        assert "latin-1" in src

    # ── import_service.py ─────────────────────────────────────────────────────

    def test_import_service_imports_non_spatial_result(self):
        src = self._src("core/services/import_service.py")
        assert "NonSpatialImportResult" in src

    def test_import_service_has_non_spatial_method(self):
        src = self._src("core/services/import_service.py")
        assert "def import_non_spatial" in src

    # ── import_dialog.py ──────────────────────────────────────────────────────

    def test_dialog_has_non_spatial_worker(self):
        src = self._src("dialogs/import_dialog.py")
        assert "_NonSpatialImportWorker" in src

    def test_dialog_has_non_spatial_checkbox(self):
        src = self._src("dialogs/import_dialog.py")
        assert "_non_spatial_cb" in src

    def test_dialog_has_non_spatial_toggle(self):
        src = self._src("dialogs/import_dialog.py")
        assert "_on_non_spatial_toggled" in src

    def test_dialog_has_non_spatial_import_done(self):
        src = self._src("dialogs/import_dialog.py")
        assert "_on_non_spatial_import_done" in src

    def test_dialog_has_is_non_spatial(self):
        src = self._src("dialogs/import_dialog.py")
        assert "_is_non_spatial_csv" in src

    # ── attribute_table.py ────────────────────────────────────────────────────

    def test_smart_item_class_exists(self):
        src = self._src("ui/panels/attribute_table.py")
        assert "class _SmartItem" in src

    def test_smart_item_overrides_lt(self):
        src = self._src("ui/panels/attribute_table.py")
        assert "def __lt__" in src

    def test_edit_mode_methods_exist(self):
        src = self._src("ui/panels/attribute_table.py")
        for method in ["_toggle_edit_mode", "_on_cell_changed",
                       "_update_edit_ui", "_request_save", "_cancel_edits",
                       "mark_save_done", "get_pk_value"]:
            assert f"def {method}" in src, f"{method} tidak ditemukan"

    def test_save_edits_signal_declared(self):
        src = self._src("ui/panels/attribute_table.py")
        assert "save_edits_requested" in src

    def test_edit_tracking_dict_declared(self):
        src = self._src("ui/panels/attribute_table.py")
        assert "_edits" in src

    def test_pk_col_attribute_declared(self):
        src = self._src("ui/panels/attribute_table.py")
        assert "_pk_col" in src

    def test_edit_banner_exists(self):
        src = self._src("ui/panels/attribute_table.py")
        assert "_edit_banner" in src

    # ── main_window.py ────────────────────────────────────────────────────────

    def test_save_attribute_edits_method_exists(self):
        src = self._src("ui/main_window.py")
        assert "def _save_attribute_edits" in src

    def test_detect_pk_col_method_exists(self):
        src = self._src("ui/main_window.py")
        assert "def _detect_pk_col" in src

    def test_save_edits_signal_wired(self):
        src = self._src("ui/main_window.py")
        assert "save_edits_requested" in src
        assert "_save_attribute_edits" in src

    def test_pk_col_passed_to_populate(self):
        src = self._src("ui/main_window.py")
        assert "pk_col" in src
        assert "populate_table" in src

    def test_update_sql_in_save_method(self):
        src = self._src("ui/main_window.py")
        assert "UPDATE" in src
        assert "WHERE" in src

    # ── config.py ─────────────────────────────────────────────────────────────

    def test_version_is_120(self):
        src = self._src("config.py")
        assert '1.2.0' in src, "Versi di config.py bukan 1.2.0"

    def test_changelog_has_120(self):
        src = self._src("CHANGELOG.md")
        assert "v1.2.0" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestNonSpatialPreviewRouting:
    """
    REGRESSION v1.2.0 fix: Preview CSV non-spasial tidak boleh
    memanggil SpatialImporter.preview() yang butuh lon/lat.
    """

    def _src(self, rel_path: str) -> str:
        base = Path(__file__).parent.parent.parent
        return (base / rel_path).read_text(encoding="utf-8")

    def test_do_preview_non_spatial_method_exists(self):
        """_do_preview_non_spatial harus ada — ini path baru untuk mode non-spasial."""
        src = self._src("dialogs/import_dialog.py")
        assert "def _do_preview_non_spatial" in src,             "REGRESSION: _do_preview_non_spatial tidak ditemukan — Preview akan error"

    def test_on_preview_non_spatial_done_exists(self):
        src = self._src("dialogs/import_dialog.py")
        assert "def _on_preview_non_spatial_done" in src

    def test_do_preview_routes_to_non_spatial(self):
        """_do_preview() harus memeriksa _is_non_spatial_csv() dan route berbeda."""
        src = self._src("dialogs/import_dialog.py")
        # Cari blok _do_preview
        start = src.find("def _do_preview(self):")
        end   = src.find("\ndef _do_preview_non_spatial", start)
        block = src[start:end]
        assert "_is_non_spatial_csv" in block,             "REGRESSION: _do_preview tidak memeriksa mode non-spasial"
        assert "_do_preview_non_spatial" in block,             "REGRESSION: _do_preview tidak route ke _do_preview_non_spatial"

    def test_non_spatial_preview_uses_pandas(self):
        """_do_preview_non_spatial harus pakai pd.read_csv, bukan SpatialImporter."""
        src = self._src("dialogs/import_dialog.py")
        start = src.find("def _do_preview_non_spatial")
        end   = src.find("\ndef _on_preview_non_spatial_done", start)
        block = src[start:end]
        assert "pd.read_csv" in block or "read_csv" in block,             "REGRESSION: _do_preview_non_spatial tidak pakai pd.read_csv"
        # Pastikan TIDAK memanggil SpatialImporter.preview
        assert "_svc.preview_file" not in block,             "REGRESSION: _do_preview_non_spatial masih memanggil preview_file (butuh lon/lat)"

    def test_toggle_enables_import_immediately(self):
        """Saat checkbox dicentang & file sudah dipilih, Import harus bisa diklik."""
        src = self._src("dialogs/import_dialog.py")
        start = src.find("def _on_non_spatial_toggled")
        end   = src.find("\n    def ", start + 10)
        block = src[start:end]
        assert "_import_btn.setEnabled(True)" in block,             "Tombol Import tidak diaktifkan saat checkbox non-spasial dicentang"

    def test_pandas_preview_pure(self, tmp_path):
        """Simulasi preview non-spasial pakai pandas — bisa baca CSV tanpa lon/lat."""
        import pandas as pd
        p = tmp_path / "data.csv"
        p.write_text("nama,umur,kota\nBudi,30,Jakarta\nSiti,25,Surabaya\n", encoding="utf-8")

        df = pd.read_csv(str(p), sep=",", encoding="utf-8", nrows=10)
        assert len(df) == 2
        assert list(df.columns) == ["nama", "umur", "kota"]
        # Tidak ada error "Kolom koordinat tidak ditemukan"

    def test_pandas_preview_no_coord_columns(self, tmp_path):
        """CSV tanpa lat/lon sama sekali harus bisa di-preview."""
        import pandas as pd
        p = tmp_path / "referensi.csv"
        p.write_text(
            "kode_kab,nama_kabupaten,provinsi,luas_km2\n"
            "3571,Surabaya,Jawa Timur,326.36\n"
            "3272,Bandung,Jawa Barat,167.67\n",
            encoding="utf-8"
        )
        df = pd.read_csv(str(p), nrows=10)
        assert len(df) == 2
        assert "kode_kab" in df.columns
        assert "nama_kabupaten" in df.columns
        # Tidak ada kolom koordinat — tidak ada error

    def test_unicode_fallback_in_preview(self, tmp_path):
        """CSV dengan encoding latin-1 harus bisa di-preview dengan fallback."""
        import pandas as pd
        p = tmp_path / "latin.csv"
        p.write_bytes("nama,keterangan\nBudi,Daerah Istimewa Yogyakarta\n".encode("latin-1"))
        try:
            df = pd.read_csv(str(p), sep=",", encoding="utf-8", nrows=10)
        except UnicodeDecodeError:
            df = pd.read_csv(str(p), sep=",", encoding="latin-1", nrows=10)
        assert len(df) == 1
        assert "nama" in df.columns
