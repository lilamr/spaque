# Panduan Import File Spasial & Non-Spasial

Import adalah fitur untuk memuat file dari komputer ke database PostgreSQL/PostGIS. Tersedia di menu **Database → Import File Spasial** atau tombol **📂 Import** di toolbar (`Ctrl+I`).

---

## Format yang Didukung

| Format | Ekstensi | Keterangan |
|---|---|---|
| ESRI Shapefile | `.shp` | Format klasik, baca semua file pendukung (.dbf, .shx, .prj) |
| GeoJSON | `.geojson`, `.json` | Format web standar, mendukung berbagai geometry type |
| GeoPackage | `.gpkg` | Format modern satu file, direkomendasikan |
| KML / KMZ | `.kml`, `.kmz` | Format Google Earth |
| MapInfo TAB | `.tab` | Format MapInfo |
| MapInfo MIF | `.mif` | Format MapInfo interchange |
| GML | `.gml` | Format XML spasial OGC |
| GPX | `.gpx` | Format track/waypoint GPS |
| FlatGeobuf | `.fgb` | Format cloud-native cepat |
| DXF (AutoCAD) | `.dxf` | Format CAD |
| FileGDB | `.gdb` | ESRI File Geodatabase |
| **CSV / TXT** | `.csv`, `.txt`, `.tsv` | Tabel dengan atau tanpa kolom koordinat |

---

## Antarmuka Dialog Import

Dialog Import memiliki 6 bagian (section):

```
┌──────────────┬──────────────────────────────────────────────────────┐
│   IMPORT     │  ① Pilih File                                        │
│  ① Pilih     │  ② Target Database                                   │
│  ② Target    │  ③ Sistem Koordinat                                   │
│  ③ Koordinat │  ④ Primary Key                                        │
│  ④ PK        │  ⑤ Opsi CSV (hanya untuk file CSV)                   │
│  ⑤ CSV       │  ⑥ Preview Data                                       │
│  ⑥ Preview   │  [Tutup]  [👁 Preview]  [⬆ Import ke PostGIS]        │
└──────────────┴──────────────────────────────────────────────────────┘
```

---

## ① Pilih File

Klik **Browse** atau drag-drop file ke zona upload. Informasi format dan ukuran file ditampilkan otomatis.

- Klik Browse → pilih file spasial
- Nama tabel target diisi otomatis dari nama file (tanpa ekstensi)
- Format file dideteksi dari ekstensi

---

## ② Target Database

| Field | Keterangan | Default |
|---|---|---|
| **Schema** | Schema database tujuan | `public` |
| **Nama Tabel** | Nama tabel yang akan dibuat | (dari nama file) |
| **Jika Sudah Ada** | Aksi jika tabel sudah ada | Batalkan |
| **Kolom Geometri** | Nama kolom geometri di PostGIS | `geom` |

**Pilihan "Jika Sudah Ada":**
- **Batalkan jika ada** — import dibatalkan jika tabel sudah ada
- **Timpa (DROP+CREATE)** — hapus tabel lama, buat baru
- **Tambahkan baris** — tambah baris ke tabel yang sudah ada (harus skema sama)

---

## ③ Sistem Koordinat (CRS)

Spaque mendeteksi CRS dari file secara otomatis dan menampilkannya di bagian **Terdeteksi**.

### Override CRS Sumber
Aktifkan **Override CRS sumber** dan isi nomor EPSG jika:
- CRS tidak terdeteksi (umum pada DXF, CSV)
- CRS terdeteksi salah

### Reproject
Aktifkan **Reproject ke** untuk mengubah CRS sebelum data masuk ke PostGIS. Pilih CRS target dari dropdown:

| CRS | EPSG |
|---|---|
| WGS 84 | 4326 |
| Web Mercator | 3857 |
| UTM Zone 47S | 32747 |
| UTM Zone 48S | 32748 |
| UTM Zone 49S | 32749 |
| UTM Zone 50S | 32750 |
| UTM Zone 51S | 32751 |
| DGN95 | 4755 |

---

## ④ Primary Key

Bagian ini menentukan bagaimana Primary Key dibuat setelah import.

> Primary Key diperlukan untuk fitur **Edit Atribut** di Tabel Atribut. Tanpa PK, data bisa dilihat tapi tidak bisa diedit melalui antarmuka Spaque.

### Tiga Strategi PK

#### Buat otomatis (_gid) — **Direkomendasikan**
Tambahkan kolom `_gid SERIAL PRIMARY KEY` secara otomatis setelah import. Kolom ini berisi nomor urut unik (1, 2, 3, …) yang dibuat database.

```sql
ALTER TABLE public.nama_tabel ADD COLUMN _gid SERIAL PRIMARY KEY;
```

#### Pilih kolom existing
Jadikan kolom yang sudah ada di data sebagai PK. Dropdown kolom terisi otomatis setelah klik **Preview**. Spaque mencoba mendeteksi kandidat PK berdasarkan nama kolom (`gid`, `id`, `fid`, dll.).

> Syarat: kolom yang dipilih harus berisi nilai unik dan tidak boleh NULL.

#### Tanpa PK
Tidak membuat PK. Data berhasil diimport tapi fitur Edit Atribut tidak tersedia. Bisa ditambahkan belakangan via SQL Console:
```sql
ALTER TABLE public.nama_tabel ADD COLUMN _gid SERIAL PRIMARY KEY;
```

---

## ⑤ Opsi CSV

Bagian ini muncul hanya untuk file CSV/TXT/TSV.

### Import Spasial (dengan Koordinat)
Jika CSV memiliki kolom longitude/latitude, Spaque mendeteksi otomatis kolom dengan nama umum:
- **Longitude:** `lon`, `long`, `longitude`, `x`, `bujur`
- **Latitude:** `lat`, `latitude`, `y`, `lintang`

Jika nama kolom berbeda, tentukan manual di field **Kolom Longitude** dan **Kolom Latitude**.

### Import Non-Spasial (tanpa Koordinat)
Centang **"Import sebagai tabel atribut biasa (tanpa geometri)"**. Field koordinat disembunyikan. Data disimpan sebagai tabel PostgreSQL biasa via `pandas.to_sql()`.

**Opsi CSV:**

| Opsi | Pilihan |
|---|---|
| Delimiter | `,` (koma), `;` (titik koma), `\t` (tab), spasi |
| Encoding | utf-8, utf-8-sig, latin-1, cp1252, ascii |

> Encoding fallback otomatis: jika UTF-8 gagal, Spaque mencoba latin-1.

---

## ⑥ Preview Data

Klik **👁 Preview** untuk membaca 10 baris pertama file tanpa menulis ke database.

Informasi yang ditampilkan:
- Jumlah fitur total
- Tipe geometri
- CRS yang terdeteksi
- Jumlah kolom

Setelah preview:
- Dropdown kolom PK (jika strategi "Pilih kolom existing") terisi otomatis
- Tombol **⬆ Import ke PostGIS** aktif

---

## Import: Langkah Lengkap

### Import File Spasial (SHP/GeoJSON/GPKG)
1. Klik **📂 Import** di toolbar
2. Klik **Browse** → pilih file
3. Isi **Schema** dan **Nama Tabel** (atau biarkan default)
4. Pilih strategi **Primary Key** (default: Buat otomatis _gid)
5. Klik **👁 Preview** untuk verifikasi data
6. Klik **⬆ Import ke PostGIS**
7. Layer baru otomatis muncul di Layer Panel

### Import CSV dengan Koordinat
1. Pilih file `.csv`
2. Di bagian ⑤ CSV: pastikan kolom Longitude dan Latitude terdeteksi
3. Set CRS sumber (biasanya EPSG:4326 untuk data GPS)
4. Pilih strategi PK → klik Preview → Import

### Import CSV Non-Spasial
1. Pilih file `.csv`
2. Di bagian ⑤ CSV: centang **"Import sebagai tabel atribut biasa"**
3. Pilih strategi PK (disarankan: Buat otomatis _gid)
4. Klik Preview → Import
5. Tabel muncul di Layer Panel dengan ikon 📋
6. Double-klik untuk melihat data di Tabel Atribut

---

## Setelah Import

- Layer baru otomatis muncul di **Layer Panel**
- Untuk layer spasial: data langsung tampil di peta
- Untuk tabel non-spasial: double-klik untuk buka di Tabel Atribut
- Tabel tersimpan permanen di PostgreSQL — tetap ada meski Spaque ditutup

---

## Perbaikan Geometri Otomatis

Spaque otomatis memperbaiki data sebelum import:
- **Geometri null** — baris dengan geometri kosong dihapus (dilaporkan di warning)
- **Geometri tidak valid** — diperbaiki via `buffer(0)` trick (dilaporkan di warning)

Warning ditampilkan di kotak kuning setelah import selesai.

---

## Troubleshooting Import

| Masalah | Penyebab | Solusi |
|---|---|---|
| CRS tidak terdeteksi | File tidak punya info CRS | Set manual di Override CRS sumber |
| Error GDAL saat baca file | File rusak atau format tidak didukung | Konversi dulu dengan QGIS |
| Encoding error CSV | Karakter non-ASCII | Ganti encoding ke latin-1 atau cp1252 |
| Koordinat tidak terdeteksi (CSV) | Nama kolom tidak umum | Set manual Kolom Longitude/Latitude |
| Tabel sudah ada | Nama tabel duplikat | Ubah nama tabel atau pilih "Timpa" |
| PK gagal dibuat | Kolom pilihan ada nilai duplikat | Pilih kolom lain atau gunakan "Buat otomatis" |
| Kolom nama panjang | SHP: max 10 karakter per kolom | Ekspor ke GeoJSON/GPKG dulu |
