"""
dialogs/help_dialog.py
Jendela bantuan dengan tampilan dokumentasi Markdown.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QTextBrowser,
    QPushButton, QFrame, QLabel,
)

from config import AppConfig


# ── Dokumen yang tersedia ─────────────────────────────────────────────────────

DOCS = [
    {
        "title": "🏠  Tentang Spaque",
        "file":  None,   # konten inline
        "content": f"""# 🌍 Spaque — PostGIS Desktop GIS

**Versi:** {AppConfig.APP_VERSION}

Spaque adalah aplikasi desktop GIS untuk eksplorasi, query, dan analisis data spasial berbasis **PostgreSQL/PostGIS**. Dirancang untuk pengguna yang ingin melakukan geoprocessing dan query atribut secara visual tanpa menulis SQL secara manual.

---

## Fitur Utama

| Fitur | Keterangan |
|---|---|
| 📂 **Import File Spasial** | SHP, GeoJSON, GPKG, KML, CSV, GDB, dll. |
| 🔍 **Query Builder Visual** | Filter atribut tanpa SQL |
| ⚙ **Geoprocessing** | Buffer, Clip, Intersect, Union, dan 20+ operasi lainnya |
| 🗺 **Peta Interaktif** | Visualisasi hasil dengan Leaflet.js |
| 💾 **Save/Load Project** | Simpan sesi kerja ke file .spq |
| ⬇ **Export** | GeoJSON, Shapefile, CSV |

---

## Cara Mulai

1. Klik **🔌 Koneksi** dan masukkan kredensial PostgreSQL/PostGIS
2. Layer yang tersedia muncul di **Layer Panel** kiri
3. Double-klik layer untuk menampilkan di peta
4. Gunakan **Query Builder** untuk filter data
5. Gunakan **Geoprocessing** untuk analisis spasial

---

## Stack Teknologi

- **Python** — bahasa pemrograman utama
- **PyQt6** — framework GUI
- **GeoPandas** — pengolahan data spasial
- **PostGIS** — database spasial
- **Leaflet.js** — visualisasi peta interaktif
- **Shapely** — operasi geometri
- **Folium** — render HTML peta

---

## Kontak & Kontribusi

GitHub: [github.com/lilamr/spaque](https://github.com/lilamr/spaque)
""",
    },
    {
        "title": "🔌  Koneksi Database",
        "file":  None,
        "content": """# Koneksi ke Database PostGIS

Spaque membutuhkan koneksi ke database **PostgreSQL** dengan ekstensi **PostGIS** aktif.

---

## Langkah Koneksi

1. Klik tombol **🔌 Koneksi** di toolbar atau menu **Database → Koneksi ke PostGIS**
2. Isi form koneksi:

| Field | Keterangan | Default |
|---|---|---|
| **Host** | Alamat server PostgreSQL | `localhost` |
| **Port** | Port PostgreSQL | `5432` |
| **Database** | Nama database | *(wajib diisi)* |
| **Username** | User PostgreSQL | `postgres` |
| **Password** | Password user | *(sesuai konfigurasi)* |

3. Klik **Test Koneksi** untuk memverifikasi sebelum menghubungkan
4. Klik **Hubungkan** untuk terhubung

---

## Persyaratan Database

Database harus memiliki ekstensi PostGIS:

```sql
-- Cek apakah PostGIS sudah terinstall
SELECT PostGIS_Version();

-- Jika belum, install dengan:
CREATE EXTENSION postgis;
```

---

## Menyimpan Koneksi di Project

Setelah terhubung, simpan project (Ctrl+S) agar informasi koneksi tersimpan dan bisa di-restore saat membuka project berikutnya. Password tidak disimpan demi keamanan — Anda akan diminta memasukkan password kembali.

---

## Troubleshooting

| Error | Penyebab | Solusi |
|---|---|---|
| `connection refused` | PostgreSQL tidak berjalan | Start service PostgreSQL |
| `password authentication failed` | Password salah | Periksa password |
| `database does not exist` | Nama database salah | Periksa nama database |
| `PostGIS tidak terdeteksi` | Ekstensi PostGIS belum install | `CREATE EXTENSION postgis;` |
""",
    },
    {
        "title": "📂  Import File Spasial",
        "file":  None,
        "content": """# Import File Spasial

Spaque mendukung import berbagai format file spasial langsung ke PostGIS.

---

## Format yang Didukung

| Format | Ekstensi | Keterangan |
|---|---|---|
| ESRI Shapefile | `.shp` | Format klasik, baca semua file pendukung |
| GeoJSON | `.geojson`, `.json` | Format web standar |
| GeoPackage | `.gpkg` | Format modern, satu file |
| KML / KMZ | `.kml`, `.kmz` | Format Google Earth |
| MapInfo | `.tab`, `.mif` | Format MapInfo |
| GML | `.gml` | Format XML spasial |
| GPX | `.gpx` | Format GPS |
| FlatGeobuf | `.fgb` | Format cloud-native |
| DXF (AutoCAD) | `.dxf` | Format CAD |
| FileGDB | `.gdb` | ESRI File Geodatabase |
| **CSV + Koordinat** | `.csv`, `.txt`, `.tsv` | Tabel dengan kolom lon/lat |

---

## Langkah Import

1. Klik **📂 Import** di toolbar atau menu **Database → Import File Spasial**
2. Klik **Browse** dan pilih file
3. Isi opsi target:
   - **Schema** — schema database tujuan (default: `public`)
   - **Nama Tabel** — nama tabel yang akan dibuat (default: nama file)
   - **Jika Sudah Ada** — `Batalkan`, `Timpa`, atau `Tambahkan`
4. Atur **CRS** jika perlu override atau reproject
5. Untuk **CSV**: tentukan kolom Longitude dan Latitude
6. Klik **👁 Preview** untuk melihat 10 baris pertama
7. Klik **⬆ Import ke PostGIS**

---

## Import CSV dengan Koordinat

File CSV harus memiliki kolom koordinat. Spaque otomatis mendeteksi kolom dengan nama:

**Longitude:** `lon`, `long`, `longitude`, `x`, `bujur`  
**Latitude:** `lat`, `latitude`, `y`, `lintang`

Jika nama kolom berbeda, tentukan secara manual di bagian **Opsi CSV**.

---

## CRS dan Proyeksi

- Spaque membaca CRS dari file secara otomatis
- Jika CRS tidak terdeteksi (umum untuk DXF, CSV), set manual di bagian **Override CRS**
- Aktifkan **Reproject ke** untuk mengubah CRS sebelum masuk ke PostGIS

---

## Setelah Import

- Layer baru otomatis muncul di **Layer Panel**
- Layer langsung ditampilkan di peta
- Data tersimpan permanen di PostgreSQL
""",
    },
    {
        "title": "🔍  Query Builder",
        "file":  "panduan-query-builder.md",
        "content": None,
    },
    {
        "title": "⚙  Geoprocessing",
        "file":  "panduan-geoprocessing.md",
        "content": None,
    },
    {
        "title": "🗺  Peta dan Visualisasi",
        "file":  None,
        "content": """# Peta dan Visualisasi

Spaque menggunakan **Leaflet.js** untuk menampilkan data spasial secara interaktif.

---

## Basemap yang Tersedia

| Nama | Keterangan |
|---|---|
| **CartoDB Dark** | Basemap gelap (default) |
| **CartoDB Light** | Basemap terang |
| **OpenStreetMap** | Peta jalan detail |

Ganti basemap melalui kontrol layer di pojok kanan atas peta.

---

## Choropleth (Pewarnaan Berdasarkan Nilai)

Warnai fitur berdasarkan nilai kolom numerik:

1. Pilih kolom di dropdown **Warna** di toolbar peta
2. Pilih skema warna (palet) di dropdown **Palet**
3. Klik **↻** untuk refresh

**Palet yang tersedia:**
- `Viridis` — biru-hijau-kuning (bagus untuk umum)
- `Plasma` — ungu-merah-kuning
- `Blues`, `Greens`, `Reds` — gradasi satu warna
- `RdYlGn` — merah-kuning-hijau (bagus untuk klasifikasi)
- `Spectral` — pelangi

---

## Interaksi Peta

| Aksi | Keterangan |
|---|---|
| **Scroll / Pinch** | Zoom in / zoom out |
| **Drag** | Pan (geser peta) |
| **Hover fitur** | Tampilkan tooltip atribut |
| **Klik fitur** | Tampilkan popup detail atribut |
| **Hover polygon** | Highlight tepi polygon |

---

## Keterbatasan Peta

- Maksimum **5.000 fitur** ditampilkan per layer (performa)
- Peta membutuhkan **koneksi internet** untuk memuat basemap tiles
- Untuk data besar, pertimbangkan filter dulu via Query Builder

---

## Tips Visualisasi

- Gunakan **choropleth** untuk membandingkan nilai antar wilayah
- Layer hasil geoprocessing langsung tampil setelah operasi selesai
- Klik **↻ Refresh** di toolbar peta jika tampilan tidak update
""",
    },
    {
        "title": "💾  Manajemen Project",
        "file":  None,
        "content": """# Manajemen Project (.spq)

Spaque menyimpan seluruh sesi kerja dalam file berekstensi **.spq** (Spaque Project).

---

## Yang Tersimpan dalam File .spq

| Data | Keterangan |
|---|---|
| Informasi koneksi DB | Host, port, database, username (bukan password) |
| Layer aktif terakhir | Schema, tabel, dan query terakhir |
| State peta | Choropleth column, colormap |
| SQL Console | Isi editor terakhir |
| Ukuran jendela | Posisi dan ukuran panel |
| Riwayat query | Maksimum 50 query terakhir |
| Bookmark query | Query yang disimpan manual |

> **Keamanan:** Password tidak disimpan. Saat membuka project, Anda akan diminta memasukkan password kembali.

---

## Operasi Project

| Aksi | Menu | Shortcut |
|---|---|---|
| Project baru | Project → Baru | `Ctrl+N` |
| Buka project | Project → Buka | `Ctrl+O` |
| Simpan | Project → Simpan | `Ctrl+S` |
| Simpan sebagai | Project → Simpan Sebagai | `Ctrl+Shift+S` |
| Buka terakhir | Project → File Terakhir | — |
| Edit nama/deskripsi | Project → Properti Project | — |

---

## Format File .spq

File `.spq` adalah format biner terkompresi (gzip + JSON). Tidak dimaksudkan untuk diedit manual. Dapat dibagikan ke pengguna lain selama mereka memiliki akses ke database yang sama.

---

## Riwayat Query

Setiap query yang dijalankan otomatis tersimpan di riwayat project. Untuk melihat: buka SQL Console dan gunakan riwayat yang tersimpan.

---

## File Terakhir

Daftar project yang baru dibuka tersimpan di `~/.spaque/recent_projects.json` (Linux/macOS) atau `%USERPROFILE%\\.spaque\\recent_projects.json` (Windows).
""",
    },
    {
        "title": "⬇  Export Data",
        "file":  None,
        "content": """# Export Data

Spaque mendukung export data spasial yang sedang aktif ke berbagai format.

---

## Format Export

| Format | Ekstensi | Keterangan |
|---|---|---|
| **GeoJSON** | `.geojson` | Format web universal, CRS WGS84 |
| **Shapefile** | `.shp` | Format ESRI, kompatibel dengan semua GIS |
| **CSV** | `.csv` | Atribut saja tanpa geometri |

---

## Cara Export

1. Muat data ke peta (double-klik layer atau jalankan query)
2. Klik tombol **⬇ Export** di toolbar atau menu **Export**
3. Pilih format
4. Pilih lokasi penyimpanan
5. Klik Simpan

---

## Catatan

- Export GeoJSON otomatis dikonversi ke **WGS84 (EPSG:4326)**
- Export Shapefile: nama kolom dipotong maksimum **10 karakter** (batasan format .dbf)
- Export CSV hanya menyertakan atribut, **tidak termasuk geometri**
- Data yang diekspor adalah data yang sedang **aktif di layar** (hasil query atau layer terakhir), bukan seluruh isi tabel

---

## Export Hasil Geoprocessing

Hasil geoprocessing sudah tersimpan sebagai tabel baru di PostGIS. Untuk export:
1. Muat tabel hasil dari Layer Panel
2. Gunakan menu Export seperti biasa
""",
    },
    {
        "title": "⌨  SQL Console",
        "file":  None,
        "content": """# SQL Console

SQL Console memungkinkan query SQL bebas langsung ke PostGIS, termasuk query multi-layer dan fungsi spasial kompleks.

---

## Akses SQL Console

- Menu **Query → SQL Console**
- Tombol **⌨ SQL Console** di toolbar
- Shortcut: `Ctrl+Shift+Q`
- Tab **SQL Console** di panel bawah

---

## Contoh Query

### Query Sederhana
```sql
SELECT * FROM public.kawasan_hutan
WHERE luas > 1000
ORDER BY luas DESC
LIMIT 50
```

### Query dengan Fungsi Spasial
```sql
-- Hitung luas dalam hektar
SELECT n_kh, luas,
  ST_Area(geom::geography) / 10000 AS luas_ha
FROM public.kawasan_hutan
ORDER BY luas_ha DESC
```

### Query Multi-Layer (Join Spasial)
```sql
-- Pohon yang berada di dalam kawasan hutan
SELECT a.nama_ilmia, a.dbh, b.n_kh
FROM public.pohon a
JOIN public.kawasan_hutan b
  ON ST_Within(a.geom, b.geom)
WHERE b.n_kh = 'Hutan Lindung'
```

### Buffer dan Intersect dalam Satu Query
```sql
-- Pohon dalam radius 500m dari sungai
SELECT p.*
FROM public.pohon p
WHERE EXISTS (
  SELECT 1 FROM public.sungai s
  WHERE ST_DWithin(p.geom::geography, s.geom::geography, 500)
)
```

---

## Tips SQL Console

- Query yang menghasilkan kolom geometri akan ditampilkan di **peta**
- Query tanpa geometri hanya ditampilkan di **tabel atribut**
- Gunakan `LIMIT` untuk query besar agar tidak lambat
- Komentar SQL menggunakan `--` di awal baris
- Semua query menggunakan **read-only** — tidak bisa INSERT/UPDATE/DELETE dari console

---

## Referensi Fungsi PostGIS

| Fungsi | Keterangan |
|---|---|
| `ST_Area(geom::geography)` | Luas dalam m² |
| `ST_Length(geom::geography)` | Panjang dalam meter |
| `ST_Distance(a::geography, b::geography)` | Jarak dalam meter |
| `ST_Buffer(geom::geography, r)::geometry` | Buffer r meter |
| `ST_Intersects(a, b)` | Cek tumpang tindih |
| `ST_Within(a, b)` | Cek a di dalam b |
| `ST_Union(geom)` | Gabung geometri |
| `ST_Intersection(a, b)` | Irisan dua geometri |
| `ST_Transform(geom, srid)` | Ubah CRS |
| `ST_SRID(geom)` | Cek CRS saat ini |
""",
    },
    {
        "title": "❓  FAQ",
        "file":  None,
        "content": """# Pertanyaan yang Sering Diajukan (FAQ)

---

**Q: Peta tidak tampil, hanya halaman putih/kosong.**

A: Kemungkinan penyebab:
1. **Koneksi internet** — Basemap tiles membutuhkan internet. Cek koneksi.
2. **Layer tidak punya geometri** — Pastikan query mengikutsertakan kolom geometri.
3. **Koordinat Z (3D)** — Spaque otomatis menangani ini, tapi pastikan menggunakan versi terbaru.
4. **Leaflet belum load** — Coba klik **↻ Refresh** di toolbar peta.

---

**Q: Query Builder tidak muncul / crash saat dibuka.**

A: Pastikan sudah terhubung ke database dan ada layer spasial yang tersedia. Klik **🔄 Refresh** terlebih dahulu.

---

**Q: Apakah data di database berubah saat saya melakukan operasi di Spaque?**

A: Tidak, kecuali operasi berikut yang memang membuat tabel baru:
- **Import** — membuat tabel baru dari file
- **Geoprocessing** — membuat tabel hasil di database

Query Builder, SQL Console, dan visualisasi peta tidak mengubah data sama sekali.

---

**Q: Geoprocessing menghasilkan geometri yang salah.**

A: Pastikan:
1. CRS kedua layer **sama** atau kompatibel sebelum dioverlay
2. Untuk operasi berbasis jarak (Buffer, Select by Distance), Spaque otomatis konversi ke meter
3. Periksa preview SQL sebelum menjalankan operasi

---

**Q: Apakah bisa query dari dua layer sekaligus?**

A: Melalui **Query Builder visual** belum bisa (hanya satu layer). Tapi melalui **SQL Console** bisa dengan JOIN:
```sql
SELECT a.*, b.n_kh
FROM public.pohon a
JOIN public.kawasan_hutan b ON ST_Within(a.geom, b.geom)
```

---

**Q: Format file apa saja yang bisa diimport?**

A: SHP, GeoJSON, GPKG, KML, KMZ, TAB, MIF, GML, GPX, FGB, DXF, GDB, CSV, TXT, TSV.

---

**Q: Apakah Spaque bisa digunakan offline?**

A: Ya, untuk fungsi database dan geoprocessing. Tapi basemap peta membutuhkan internet. Untuk offline penuh, download Leaflet assets:
```bash
mkdir -p ~/.spaque/assets
wget https://unpkg.com/leaflet@1.9.4/dist/leaflet.js -O ~/.spaque/assets/leaflet.min.js
wget https://unpkg.com/leaflet@1.9.4/dist/leaflet.css -O ~/.spaque/assets/leaflet.min.css
```

---

**Q: Apa perbedaan Clip dan Intersect?**

A: Keduanya memotong layer A dengan batas layer B. Bedanya:
- **Clip** → hanya atribut dari layer A yang dibawa ke hasil
- **Intersect** → atribut dari **kedua** layer dibawa ke hasil

---

**Q: File .spq bisa dibuka di komputer lain?**

A: Bisa, asalkan komputer lain juga punya Spaque dan akses ke database yang sama. Informasi koneksi tersimpan di file, tapi password harus dimasukkan ulang.
""",
    },
]


# ── Markdown renderer sederhana → HTML ───────────────────────────────────────

def _md_to_html(md: str) -> str:
    """Convert subset Markdown ke HTML untuk QTextBrowser."""
    import re

    lines = md.split('\n')
    html_lines = []
    in_table = False
    in_code  = False
    code_buf = []

    for line in lines:
        # Code block
        if line.strip().startswith('```'):
            if not in_code:
                in_code = True
                lang = line.strip()[3:].strip()
                html_lines.append(
                    '<pre style="background:#0f1116;color:#7adb78;'
                    'padding:10px;border-radius:6px;font-family:monospace;'
                    'font-size:11px;border:1px solid #2d3340;white-space:pre-wrap;">'
                )
            else:
                in_code = False
                html_lines.append('</pre>')
            continue

        if in_code:
            html_lines.append(line.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))
            continue

        # Table
        if line.strip().startswith('|'):
            if not in_table:
                in_table = True
                html_lines.append(
                    '<table style="border-collapse:collapse;width:100%;'
                    'margin:10px 0;font-size:12px;">'
                )
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if all(set(c.replace('-','').replace(':','').strip()) == set() or c.strip().replace('-','').replace(':','') == '' for c in cells):
                continue  # separator row
            is_header = html_lines and '<table' in html_lines[-1] or \
                        (len(html_lines) >= 2 and '<table' in ''.join(html_lines[-3:]))
            tag = 'th' if '---' not in line and not any('<tr>' in l for l in html_lines[-5:]) else 'td'
            row = '<tr>' + ''.join(
                f'<{tag} style="border:1px solid #2d3340;padding:5px 8px;'
                f'background:{"#13151a" if tag=="th" else "transparent"};'
                f'color:{"#c0cad8" if tag=="th" else "#a0aab8"};">{c}</{tag}>'
                for c in cells
            ) + '</tr>'
            html_lines.append(row)
            continue
        else:
            if in_table:
                html_lines.append('</table>')
                in_table = False

        # Headings
        if line.startswith('#### '):
            html_lines.append(f'<h4 style="color:#c0cad8;margin:12px 0 4px;">{line[5:]}</h4>')
        elif line.startswith('### '):
            html_lines.append(f'<h3 style="color:#d0d8e8;border-bottom:1px solid #2d3340;padding-bottom:4px;margin:16px 0 8px;">{line[4:]}</h3>')
        elif line.startswith('## '):
            html_lines.append(f'<h2 style="color:#e0e6f0;border-bottom:1px solid #3d4455;padding-bottom:6px;margin:20px 0 10px;">{line[3:]}</h2>')
        elif line.startswith('# '):
            html_lines.append(f'<h1 style="color:#e0e6f0;font-size:18px;margin:0 0 16px;padding-bottom:8px;border-bottom:2px solid #2e5bff;">{line[2:]}</h1>')
        # HR
        elif line.strip() == '---':
            html_lines.append('<hr style="border:none;border-top:1px solid #2d3340;margin:16px 0;"/>')
        # List items
        elif line.startswith('- ') or line.startswith('* '):
            content = line[2:]
            content = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', content)
            content = re.sub(r'`(.+?)`', r'<code style="background:#1e2229;padding:1px 5px;border-radius:3px;color:#7adb78;font-size:11px;">\1</code>', content)
            html_lines.append(f'<div style="margin:2px 0 2px 16px;color:#a0aab8;">• {content}</div>')
        # Blockquote
        elif line.startswith('> '):
            content = line[2:]
            html_lines.append(
                f'<div style="border-left:3px solid #2e5bff;padding:4px 10px;'
                f'margin:8px 0;background:#1e2a3a;color:#a0aab8;font-size:11px;">'
                f'{content}</div>'
            )
        # Empty line
        elif line.strip() == '':
            html_lines.append('<br/>')
        # Normal paragraph
        else:
            content = line
            content = re.sub(r'\*\*(.+?)\*\*', r'<b style="color:#e0e6f0;">\1</b>', content)
            content = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', content)
            content = re.sub(r'`(.+?)`',
                r'<code style="background:#1e2229;padding:1px 5px;border-radius:3px;'
                r'color:#7adb78;font-size:11px;">\1</code>', content)
            content = re.sub(r'\[(.+?)\]\((.+?)\)',
                r'<a href="\2" style="color:#4a80ff;">\1</a>', content)
            html_lines.append(f'<p style="margin:4px 0;color:#a0aab8;line-height:1.7;">{content}</p>')

    if in_table:
        html_lines.append('</table>')

    return '\n'.join(html_lines)


def _load_content(doc: dict) -> str:
    """Load konten dokumen: dari file .md atau inline."""
    if doc.get("content"):
        return _md_to_html(doc["content"])

    if doc.get("file"):
        docs_dir = Path(AppConfig.APP_DIR) / "docs"
        path = docs_dir / doc["file"]
        if path.exists():
            return _md_to_html(path.read_text(encoding="utf-8"))
        return f"<p style='color:#e03c4a;'>File tidak ditemukan: {path}</p>"

    return "<p style='color:#6a7590;'>Tidak ada konten.</p>"


# ── Dialog utama ──────────────────────────────────────────────────────────────

class HelpDialog(QDialog):
    """
    Jendela bantuan dengan panel navigasi kiri dan konten kanan.
    """

    def __init__(self, parent=None, initial_page: str = "🏠  Tentang Spaque"):
        super().__init__(parent)
        self.setWindowTitle(f"Bantuan — Spaque v{AppConfig.APP_VERSION}")
        self.resize(960, 680)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self._build_ui()
        self._select_page(initial_page)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(54)
        hdr.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #1a2340,stop:1 #13151a);"
            "border-bottom:1px solid #2d3340;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 16, 0)
        icon = QLabel("📖")
        icon.setStyleSheet("font-size:22px;background:transparent;border:none;")
        title = QLabel(f"Bantuan Spaque  —  v{AppConfig.APP_VERSION}")
        title.setStyleSheet(
            "font-size:15px;font-weight:bold;color:#e0e6f0;"
            "background:transparent;border:none;"
        )
        hl.addWidget(icon)
        hl.addWidget(title)
        hl.addStretch()
        layout.addWidget(hdr)

        # Splitter: nav + content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle{background:#2d3340;}")

        # Left nav
        nav = QFrame()
        nav.setFixedWidth(210)
        nav.setStyleSheet("background:#13151a;border-right:1px solid #2d3340;")
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(0, 8, 0, 8)
        nl.setSpacing(2)

        self._nav_list = QListWidget()
        self._nav_list.setStyleSheet("""
            QListWidget {
                background:#13151a; border:none; outline:none;
                font-size:12px; color:#a0aab8;
            }
            QListWidget::item {
                padding:9px 14px; border-radius:0;
            }
            QListWidget::item:hover    { background:#1e2229; color:#e0e6f0; }
            QListWidget::item:selected {
                background:#2e5bff22; color:#6699ff;
                border-left:3px solid #2e5bff;
            }
        """)
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)

        for doc in DOCS:
            item = QListWidgetItem(doc["title"])
            self._nav_list.addItem(item)

        nl.addWidget(self._nav_list)
        splitter.addWidget(nav)

        # Right content
        content_frame = QFrame()
        content_frame.setStyleSheet("background:#1a1d23;")
        cl = QVBoxLayout(content_frame)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet("""
            QTextBrowser {
                background:#1a1d23; color:#a0aab8;
                border:none; font-size:13px;
                font-family:'Segoe UI','Noto Sans',Arial,sans-serif;
                padding:20px 28px;
                line-height:1.7;
            }
            QScrollBar:vertical {
                background:#1a1d23; width:7px; border-radius:4px;
            }
            QScrollBar::handle:vertical {
                background:#3d4455; border-radius:4px; min-height:20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """)
        cl.addWidget(self._browser, 1)

        # Footer
        footer = QFrame()
        footer.setFixedHeight(46)
        footer.setStyleSheet(
            "background:#13151a;border-top:1px solid #2d3340;"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 0, 16, 0)
        self._page_label = QLabel("")
        self._page_label.setStyleSheet("color:#4a5570;font-size:11px;")
        close_btn = QPushButton("Tutup")
        close_btn.setObjectName("secondary")
        close_btn.setFixedHeight(30)
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.close)
        fl.addWidget(self._page_label, 1)
        fl.addWidget(close_btn)
        cl.addWidget(footer)

        splitter.addWidget(content_frame)
        splitter.setSizes([210, 750])
        layout.addWidget(splitter, 1)

    def _on_nav_changed(self, row: int):
        if 0 <= row < len(DOCS):
            doc = DOCS[row]
            html = _load_content(doc)
            self._browser.setHtml(
                f'<html><head><style>'
                f'body{{background:#1a1d23;color:#a0aab8;'
                f'font-family:"Segoe UI","Noto Sans",Arial,sans-serif;'
                f'font-size:13px;line-height:1.7;margin:0;padding:0;}}'
                f'</style></head><body>{html}</body></html>'
            )
            self._browser.moveCursor(self._browser.textCursor().MoveOperation.Start)
            self._page_label.setText(f"{row + 1} / {len(DOCS)}  —  {doc['title'].strip()}")

    def _select_page(self, title: str):
        for i, doc in enumerate(DOCS):
            if doc["title"].strip() == title.strip() or title in doc["title"]:
                self._nav_list.setCurrentRow(i)
                return
        self._nav_list.setCurrentRow(0)


def open_help(parent=None, page: str = ""):
    """Shortcut untuk membuka dialog bantuan."""
    dlg = HelpDialog(parent, initial_page=page or "🏠  Tentang Spaque")
    dlg.exec()
