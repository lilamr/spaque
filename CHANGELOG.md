# Changelog

## v1.2.0 (2025)

### ✨ Fitur Baru

#### 📋 Import CSV Non-Spasial
Import file CSV yang tidak memiliki kolom koordinat ke PostgreSQL sebagai tabel atribut biasa.

- Checkbox **"Import sebagai tabel atribut biasa (tanpa geometri)"** di dialog Import — aktif otomatis saat file CSV dipilih
- Ketika dipilih, field Longitude/Latitude disembunyikan otomatis
- Data disimpan ke PostgreSQL via `pandas.to_sql()`
- Fallback encoding otomatis (UTF-8 → latin-1) jika encoding gagal
- Nama kolom disanitasi otomatis ke format identifier PostgreSQL yang aman
- Tabel non-spasial muncul di **Layer Panel** dengan ikon 📋
- Double-klik untuk membuka di Tabel Atribut

#### 🔑 Konfigurasi Primary Key saat Import
Bagian baru **④ Primary Key** di dialog Import dengan tiga strategi:

- **Buat otomatis (_gid)** — tambahkan `_gid SERIAL PRIMARY KEY` setelah import (default, direkomendasikan)
- **Pilih kolom existing** — jadikan kolom yang ada sebagai PK (dropdown terisi otomatis dari Preview, auto-detect kandidat `gid`/`id`/`fid`)
- **Tanpa PK** — tidak buat PK (fitur Edit Atribut tidak tersedia)

Strategi PK berlaku untuk **semua format** file (SHP, GeoJSON, GPKG, CSV, dll.) termasuk import non-spasial.

#### ✏ Edit Atribut Layer (Tabel Atribut)
Edit nilai atribut layer langsung dari antarmuka Spaque, lalu simpan ke PostGIS.

- Tombol **✏ Edit** muncul di toolbar tabel atribut (panel bawah dan popup window)
- Syarat: tabel harus memiliki Primary Key (terdeteksi dari `information_schema` atau nama kolom)
- Double-klik sel untuk edit — sel yang diubah disorot warna kuning
- Banner hijau bertuliskan mode aktif selama edit
- Tombol **💾 Simpan** dan **✕ Batal** muncul saat ada perubahan pending
- Konfirmasi sebelum keluar mode edit jika ada perubahan belum disimpan
- Perubahan disimpan ke PostGIS via `UPDATE ... WHERE pk_col = nilai`
- Kolom geometri dan kolom PK tidak bisa diubah (terlindungi otomatis)

#### ➕ Tambah & Hapus Kolom
Di mode edit, tersedia tombol untuk mengelola struktur tabel:

- **➕ Kolom** — tambah kolom baru dengan dialog nama + tipe data
- **➖ Kolom** — hapus kolom dari tabel (konfirmasi wajib)

Tipe data yang tersedia: TEXT, INTEGER, DOUBLE PRECISION, BOOLEAN, DATE, TIMESTAMP, NUMERIC, VARCHAR(255), BIGINT.

#### ➕ Tambah Baris (Non-Spasial)
Untuk tabel non-spasial yang memiliki PK, tombol **➕ Tambah Baris** tersedia di:
- Panel bawah (bottom panel)
- Popup window attribute table

Dialog isian muncul dengan field untuk setiap kolom (maks 20 ditampilkan). Kolom PK diisi otomatis oleh database. Nilai kosong disimpan sebagai NULL.

#### 🗑 Hapus Baris
Di mode edit, klik baris lalu **🗑 Hapus Baris** untuk menghapus permanen dari database via `DELETE FROM ... WHERE pk = nilai`.

#### ↗ Popup Window Tabel Atribut
Klik **↗ Window** untuk membuka tabel atribut di jendela terpisah (seperti QGIS). Bisa dibuka beberapa popup sekaligus.

Fitur eksklusif popup window:
- **Paginasi** — 5.000 baris per halaman dengan navigasi ◀ Berikutnya ▶
- **Scroll horizontal** — tidak ada kolom yang terpotong
- **Refresh otomatis** — setelah tambah/hapus kolom, data langsung diperbarui

---

### 🐛 Perbaikan Bug

#### Popup Window Tabel Atribut
- **Scroll horizontal** — sebelumnya tabel terpotong karena `setMinimumWidth` memaksa lebar jendela; kini menggunakan `ScrollBarAsNeeded`
- **Refresh setelah DDL** — tambah/hapus kolom kini langsung terlihat di popup window tanpa perlu tutup-buka ulang
- **Save di popup window** — sebelumnya tombol Simpan di popup tidak berfungsi karena handler membaca dari bottom panel, bukan dari dialog itu sendiri; diperbaiki dengan mengirim referensi `dialog` bersama sinyal `save_edits_requested(dialog, edits)`

#### Deteksi Primary Key
- Deteksi PK kini dilakukan langsung dari `information_schema` PostgreSQL (`_detect_pk_from_db`) — lebih akurat dari heuristik nama kolom
- Mencakup kolom `_gid` yang dibuat Spaque saat geoprocessing
- Fallback heuristik tetap ada: `gid`, `id`, `fid`, `ogc_fid`, `objectid`, `_gid`, `oid`, dll.

#### Tombol Edit tanpa PK
- Sebelumnya tombol ✏ Edit muncul bahkan untuk tabel tanpa PK
- Kini tombol Edit disembunyikan jika tidak ada PK
- Muncul pesan peringatan deskriptif jika user mencoba mengakses edit tanpa PK

#### Pesan Import Non-Spasial
- Dihapus pesan keliru *"Tidak akan muncul di Layer Panel"* — tabel non-spasial sebenarnya muncul di Layer Panel dengan ikon 📋

---

### 📝 Perubahan Internal

- `core/importers/base.py`: tambah `NonSpatialImportResult`, `SpatialImporter.run_non_spatial()`, `SpatialImporter._apply_pk()`, field `pk_strategy` dan `pk_col_name` di `ImportSpec`
- `core/services/import_service.py`: tambah `ImportService.import_non_spatial()`
- `dialogs/import_dialog.py`: tambah section ④ Primary Key (`_build_pk_section`), checkbox non-spasial, `_NonSpatialImportWorker`, `_on_non_spatial_import_done()`
- `dialogs/attribute_table_dialog.py`: tulis ulang dengan paginasi (PAGE_SIZE=5000), sinyal `save_edits_requested(object, dict)`, `add_row_requested(object, dict)`, `get_pk_value_global()`, `refresh_populate()`
- `ui/panels/attribute_table.py`: tambah `_SmartItem`, edit mode, sinyal `save_edits_requested`, `add_row_requested`, `add_column_requested`, `delete_column_requested`, `delete_rows_requested`, `_on_edit_btn_clicked()`, `_on_add_row()`, `_is_spatial` flag
- `ui/main_window.py`: tambah `_detect_pk_col()`, `_detect_pk_from_db()`, `_save_attribute_edits()`, `_save_attribute_edits_from_dialog()`, `_add_row_from_dialog()`, `_add_row_from_bottom_panel()`, `_refresh_all_attr_windows()`, `_open_attribute_window()`
- `docs/panduan-tabel-atribut.md`: panduan baru
- `docs/panduan-import.md`: panduan baru


---

## v1.1.0 (2025)

### Fitur Baru: Visual Pipeline Builder

Tambahan besar pada versi ini: **Visual Pipeline Builder** (`Ctrl+P` / tombol 🔀 di toolbar).

Pipeline Builder memungkinkan pengguna membangun alur kerja analisis spasial secara visual dengan drag & drop node:

- **📦 Data Source** — pilih layer PostGIS sebagai input
- **🔍 Query Filter** — filter data dengan kondisi WHERE / ORDER BY / LIMIT
- **⚙ Geoprocessing** — jalankan operasi spasial (Buffer, Clip, Intersect, dll.)
- **💾 Output** — simpan hasil ke tabel PostGIS baru

Fitur Pipeline Builder:
- Kanvas interaktif berbasis QGraphicsScene dengan node yang bisa dipindah
- Panel properti dinamis (klik node → edit params di panel kanan)
- Koneksi antar node dengan panah bezier
- Validasi pipeline sebelum eksekusi (deteksi missing params, cycles)
- Eksekusi berurutan topological dengan progress log
- Simpan/buka pipeline sebagai file JSON untuk dipakai ulang sebagai template
- Hasil pipeline otomatis ditampilkan di peta dan tabel atribut
- Panduan lengkap di menu Bantuan → Panduan Pipeline Builder

### Perbaikan & Perubahan Lain

- Versi bump: 1.0.0 → 1.1.0
- Toolbar: tambah tombol 🔀 Pipeline di antara Geoprocessing dan SQL Console
- Menu Query: tambah entri "Visual Pipeline Builder" (Ctrl+P)
- Menu Bantuan: tambah "Panduan Pipeline Builder"

---

## v1.0.0 (2025)

Rilis perdana Spaque — PostGIS Desktop GIS.

- Koneksi PostgreSQL/PostGIS
- Import file spasial (SHP, GeoJSON, GPKG, KML, CSV, GDB, dll.)
- Query Builder Visual (WHERE tanpa SQL)
- Geoprocessing: 23 operasi (Buffer, Clip, Intersect, Centroid, Hitung Luas, dll.)
- Peta interaktif Leaflet.js dengan choropleth
- Export GeoJSON / Shapefile / CSV
- Save/Load Project (.spq)
- SQL Console bebas
- 77+ unit tests

---
