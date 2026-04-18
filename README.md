# Spaque — Spasial Query and Geoprocessing PostGIS

<div align="center">

<img src="spaque/assets/icons/icon.png" width="120" alt="SpaQue Logo">

[![GitHub](https://img.shields.io/badge/GitHub-lilamr%2Fspaque-blue?logo=github)](https://github.com/lilamr/spaque)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.6%2B-green)](https://pypi.org/project/PyQt6/)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.0%2B-orange)](https://postgis.net)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.2.0-brightgreen)]()

Desktop GIS berbasis Python untuk **geoprocessing** dan **query spasial visual** via PostGIS.
Semua operasi dilakukan dengan klik-pilih dari menu — tanpa menulis SQL secara manual.

</div>

---

## Fitur

| Kategori | Operasi |
|---|---|
| **Import File** | SHP, GeoJSON, GPKG, KML/KMZ, TAB, GML, GPX, FGB, DXF, GDB, CSV/TXT + CSV non-spasial |
| **Import PK** | Tiga strategi PK saat import: buat otomatis (`_gid`), pilih kolom existing, atau tanpa PK |
| **Query Visual** | WHERE builder (AND/OR, semua operator SQL), ORDER BY, LIMIT |
| **Pipeline Builder** | Visual Pipeline Builder — drag & drop node: Source → Query → Geoprocessing → Output |
| **Overlay** | Buffer, Intersect, Union, Clip, Difference, Symmetric Difference |
| **Geometri** | Centroid, Point on Surface, Convex Hull, Envelope, Simplify, Dissolve, Reproject, Voronoi, Delaunay |
| **Kalkulasi** | Hitung Luas/Panjang/Perimeter (akurat di ellipsoid), Statistik Spasial |
| **Seleksi Spasial** | Select by Location, Select by Distance, Nearest Neighbor (KNN) |
| **Gabung** | Spatial Join |
| **Edit Atribut** | Edit nilai sel inline, tambah/hapus kolom, tambah baris (non-spasial), simpan ke PostGIS |
| **Tabel Non-Spasial** | Import, tampilkan, dan edit tabel CSV tanpa geometri — muncul di Layer Panel (ikon 📋) |
| **Export** | GeoJSON, Shapefile, CSV |
| **Peta** | Leaflet.js interaktif, Choropleth, multi-basemap |
| **Project** | Save/Load sesi kerja (.spq) |

---

## Instalasi

### Persyaratan Sistem

| Komponen | Versi Minimum |
|---|---|
| Python | 3.10 |
| PostgreSQL | 12 |
| PostGIS | 3.0 |
| RAM | 4 GB (8 GB direkomendasikan) |

---

### 🐧 Linux (Ubuntu / Debian)

```bash
# 1. Install dependensi sistem
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git \
  libgdal-dev gdal-bin libgeos-dev libproj-dev \
  postgresql postgresql-contrib postgis

# 2. Kloning
git clone https://github.com/lilamr/spaque.git
cd spaque

# 3. Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Dependensi Python
pip install --upgrade pip
pip install -r requirements.txt

# 5. Konfigurasi
cp .env.example .env
nano .env   # isi sesuai koneksi PostgreSQL

# 6. Aktifkan PostGIS di database
psql -U postgres -d nama_database -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 7. Jalankan
python main.py
```

> **Jika error GDAL:**
> ```bash
> pip install GDAL==$(gdal-config --version)
> ```

> **Jika error libEGL (headless server):**
> ```bash
> sudo apt install libegl1 libgl1-mesa-glx
> ```

---

### 🪟 Windows 10 / 11

**1. Install Python 3.10+**
Download dari [python.org](https://www.python.org/downloads/) — centang **"Add Python to PATH"**

**2. Install PostgreSQL + PostGIS**
Download dari [postgresql.org](https://www.postgresql.org/download/windows/).
Saat instalasi, buka **Stack Builder** dan pilih **PostGIS**.

**3. Kloning dan setup:**
```cmd
git clone https://github.com/lilamr/spaque.git
cd spaque

python -m venv .venv
.venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

> **Jika error `fiona` atau `GDAL`** — install wheel dari
> [Gohlke's repository](https://www.lfd.uci.edu/~gohlke/pythonlibs/):
> ```cmd
> pip install GDAL-x.x.x-cpXXX-win_amd64.whl
> pip install Fiona-x.x.x-cpXXX-win_amd64.whl
> ```

**4. Konfigurasi:**
```cmd
copy .env.example .env
notepad .env
```

**5. Aktifkan PostGIS** (via pgAdmin atau psql):
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

**6. Jalankan:**
```cmd
python main.py
```

Buat shortcut `jalankan.bat`:
```bat
@echo off
cd /d %~dp0
.venv\Scripts\python.exe main.py
```

---

### 🍎 macOS (12+)

```bash
# 1. Install Homebrew (jika belum)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install dependensi
brew install python@3.12 git gdal proj geos postgresql@16 postgis

# 3. Start PostgreSQL
brew services start postgresql@16

# 4. Kloning
git clone https://github.com/lilamr/spaque.git
cd spaque

# 5. Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 6. Dependensi Python
pip install --upgrade pip
pip install -r requirements.txt

# 7. Konfigurasi
cp .env.example .env
nano .env

# 8. PostGIS
psql -d nama_database -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 9. Jalankan
python main.py
```

> **macOS Apple Silicon (M1/M2/M3):**
> ```bash
> pip install PyQt6-WebEngine --no-binary PyQt6-WebEngine
> ```

---

### 🐳 Docker PostgreSQL+PostGIS (Opsional)

```bash
docker run -d \
  --name spaque-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=gis_db \
  -p 5432:5432 \
  postgis/postgis:16-3.4
```

Isi `.env`:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=gis_db
DB_USER=postgres
DB_PASSWORD=postgres
```

---

## Update ke Versi Terbaru

```bash
cd spaque
git pull origin main
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt --upgrade
```

---

## Cara Pakai

1. Klik **🔌 Koneksi** → isi kredensial PostgreSQL/PostGIS
2. Double-klik layer di panel kiri untuk tampilkan di peta
3. **📂 Import** → import file spasial (atau CSV non-spasial) ke PostGIS
4. **🔍 Query Builder** → filter data visual tanpa SQL
5. **⚙ Geoprocessing** → analisis spasial (Buffer, Clip, Intersect, dll.)
6. **📋 Tabel Atribut** → lihat, edit, tambah/hapus kolom dan baris
7. **⬇ Export** → export ke GeoJSON/SHP/CSV
8. **Ctrl+S** → simpan project ke file `.spq`

Lihat panduan lengkap di menu **Bantuan (F1)** atau folder `docs/`.

---

## Struktur Proyek

```
spaque/
├── main.py                ← Entry point
├── config.py              ← Konfigurasi .env
├── requirements.txt
├── docs/
│   ├── panduan-query-builder.md
│   ├── panduan-geoprocessing.md
│   ├── panduan-tabel-atribut.md
│   ├── panduan-import.md
│   ├── panduan-pipeline-builder.md
│   └── panduan-sql-console.md
├── core/
│   ├── database/          ← Koneksi & repository PostgreSQL
│   ├── domain/            ← Entities & value objects
│   ├── geoprocessing/     ← 23 operasi geoprocessing
│   ├── importers/         ← Import file spasial
│   ├── exporters/         ← Export data
│   ├── project/           ← Save/load .spq
│   └── services/          ← Business logic
├── ui/
│   ├── main_window.py
│   ├── panels/            ← Layer browser, peta, tabel atribut
│   ├── widgets/           ← Query builder, toolbar
│   └── components/        ← Global stylesheet
├── dialogs/               ← Semua dialog popup + help
├── utils/                 ← Logger, constants, helpers
└── tests/unit/            ← 77+ unit tests
```

---

## Menjalankan Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Troubleshooting

| Masalah | Solusi |
|---|---|
| `ModuleNotFoundError: PyQt6` | `pip install PyQt6 PyQt6-WebEngine` |
| `ModuleNotFoundError: fiona` | `pip install fiona` |
| PostGIS tidak terdeteksi | Jalankan `CREATE EXTENSION postgis;` |
| Peta kosong/putih | Cek koneksi internet untuk basemap tiles |
| `libEGL.so not found` (Linux) | `sudo apt install libegl1` |
| Error GDAL di Windows | Install wheel dari Gohlke's repository |
| Layer Z tidak tampil di peta | Update ke versi terbaru — sudah diperbaiki |
| Tabel non-spasial tidak bisa diedit | Tambah PK: `ALTER TABLE t ADD COLUMN _gid SERIAL PRIMARY KEY` |
| Tombol ✏ Edit tidak muncul | Tabel tidak punya PK — lihat panduan Tabel Atribut |
| Scroll tabel terpotong | Update ke v1.2.0 — sudah diperbaiki |
| Tambah baris tidak tersedia | Hanya untuk tabel non-spasial dengan PK |

---

## Panduan Lengkap

- [Panduan Import](docs/panduan-import.md)
- [Panduan Tabel Atribut](docs/panduan-tabel-atribut.md)
- [Panduan Query Builder](docs/panduan-query-builder.md)
- [Panduan Geoprocessing](docs/panduan-geoprocessing.md)
- [Panduan Pipeline Builder](docs/panduan-pipeline-builder.md)
- [Panduan SQL Console](docs/panduan-sql-console.md)
- Bantuan in-app: tekan **F1** atau menu **Bantuan**

---

## Kontribusi

1. Fork repository
2. Buat branch: `git checkout -b fitur-baru`
3. Commit: `git commit -m 'feat: tambah fitur X'`
4. Push dan buat Pull Request

---

## Lisensi

MIT License — lihat [LICENSE](LICENSE)

Copyright © 2025 [lilamr](https://github.com/lilamr)
