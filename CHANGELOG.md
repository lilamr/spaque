# Changelog

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
