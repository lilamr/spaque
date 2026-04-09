# Panduan Visual Pipeline Builder

Pipeline Builder adalah fitur untuk membangun alur kerja analisis spasial secara visual — tanpa menulis kode. Setiap langkah diwakili oleh **node** yang saling terhubung membentuk alur data dari sumber hingga output.

Buka melalui: menu **Query → Visual Pipeline Builder**, tombol **🔀 Pipeline** di toolbar, atau shortcut `Ctrl+P`.

---

## Konsep Dasar

Pipeline adalah serangkaian **node** yang terhubung secara berurutan. Data mengalir dari node pertama ke node terakhir, dan setiap node melakukan satu tugas tertentu.

```
[📦 Data Source] → [🔍 Query Filter] → [⚙ Geoprocessing] → [💾 Output]
```

### Tipe Node

| Node | Ikon | Fungsi | Wajib? |
|---|---|---|---|
| **Data Source** | 📦 | Mengambil data dari tabel PostGIS sebagai input | Ya (minimal 1) |
| **Query Filter** | 🔍 | Menyaring data dengan kondisi WHERE, ORDER BY, LIMIT | Tidak |
| **Geoprocessing** | ⚙ | Menjalankan operasi spasial (Buffer, Clip, Intersect, dll.) | Tidak |
| **Output** | 💾 | Menentukan nama tabel hasil akhir pipeline di PostGIS | Ya (minimal 1) |

---

## Antarmuka Pipeline Builder

```
┌─────────────────────────────────────────────────────────────────────┐
│  🔀 Visual Pipeline Builder  [Nama Pipeline]  [📂 Buka] [💾 Simpan] │
│                              [🗑 Reset]  [▶ Jalankan Pipeline] [✕]  │
├──────────────┬──────────────────────────────────────┬───────────────┤
│              │                                      │               │
│  TAMBAH NODE │         KANVAS PIPELINE              │  PROPERTI     │
│              │   (area drag & drop node)            │  NODE         │
│  📦 Source   │                                      │  (form edit   │
│  🔍 Query    │   [Node]──→──[Node]──→──[Node]       │   parameter   │
│  ⚙ Geoprcs  │                                      │   node aktif) │
│  💾 Output   │   Sambungkan: [From ▼] → [To ▼]     │               │
│              │   [Sambungkan]                       │               │
├──────────────┴──────────────────────────────────────┴───────────────┤
│  📜 LOG  Menjalankan node: 📦 Source... ✅ Buffer 100m → hasil       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Langkah-Langkah Membuat Pipeline

### 1. Tambah Node

Klik tombol di **panel kiri** untuk menambahkan node ke kanvas:

- **📦 Data Source** — muncul di kanvas, otomatis terisi layer pertama
- **🔍 Query Filter** — untuk menyaring data sebelum diproses
- **⚙ Geoprocessing** — pilih operasi spasial
- **💾 Output** — tandai tabel tujuan hasil akhir

> **Tips:** Susun dari kiri ke kanan mengikuti alur data: Source → (Query) → (Geoprocess) → Output.

---

### 2. Edit Parameter Node

Klik node di kanvas → form parameter muncul di **panel kanan**.

#### Parameter: Data Source 📦

| Parameter | Keterangan |
|---|---|
| **Layer** | Pilih tabel PostGIS sebagai sumber data |
| **Limit** | Maksimum jumlah fitur yang diambil (default 5000) |

#### Parameter: Query Filter 🔍

| Parameter | Keterangan |
|---|---|
| **Tabel** | Tabel yang di-query (referensi untuk SQL) |
| **WHERE** | Kondisi filter SQL bebas, misal: `"luas" > 1000 AND "n_kh" = 'HL'` |
| **Order By** | Nama kolom untuk pengurutan (opsional) |
| **Arah** | ASC (kecil ke besar) atau DESC (besar ke kecil) |
| **Limit** | Maksimum baris hasil (0 = semua) |

> **Catatan:** Panel **Preview SQL** menampilkan SQL yang akan dijalankan secara real-time saat Anda mengetik.

#### Parameter: Geoprocessing ⚙

| Parameter | Keterangan |
|---|---|
| **Operasi** | Pilih dari 23 operasi spasial (Buffer, Clip, Intersect, dll.) |
| **Layer Overlay** | Layer kedua untuk operasi overlay (Intersect, Clip, dll.) |
| **Jarak** | Radius dalam meter (untuk Buffer, Select by Distance) |
| **Dissolve** | Gabung semua geometri hasil menjadi satu |
| **Tabel Output** | Nama tabel sementara hasil operasi ini |
| **Schema** | Schema database untuk tabel output |

#### Parameter: Output 💾

| Parameter | Keterangan |
|---|---|
| **Nama Tabel** | Nama tabel final hasil pipeline di PostGIS |
| **Schema** | Schema database (default: `public`) |

---

### 3. Sambungkan Node

Gunakan dropdown **Sambungkan** di toolbar kanvas:

1. Pilih node asal di dropdown **From**
2. Pilih node tujuan di dropdown **To**
3. Klik tombol **Sambungkan**

Koneksi akan digambar sebagai panah bezier di kanvas. Satu node bisa menjadi input untuk lebih dari satu node berikutnya.

> **Kanan-klik node** untuk menu konteks: **Edit Parameter** atau **Hapus Node**.

---

### 4. Validasi Pipeline

Sebelum dijalankan, pipeline divalidasi secara otomatis:

- ✅ Minimal ada 1 node Source dan 1 node Output
- ✅ Semua node Source sudah dipilih tabelnya
- ✅ Semua node Geoprocessing sudah dipilih operasinya
- ✅ Semua node Output sudah ada nama tabelnya
- ✅ Tidak ada siklus (loop) dalam koneksi node

Jika ada masalah, dialog validasi akan menampilkan daftar error sebelum eksekusi.

---

### 5. Jalankan Pipeline

Klik **▶ Jalankan Pipeline** di header dialog. Proses eksekusi:

1. Validasi semua node dan koneksi
2. Hitung urutan eksekusi optimal (topological sort)
3. Eksekusi setiap node secara berurutan
4. Simpan hasil ke tabel PostGIS
5. Tampilkan hasil di peta utama dan tabel atribut

Progress eksekusi ditampilkan di **panel log** (bawah dialog) secara real-time.

---

## Simpan dan Buka Pipeline

### Simpan Pipeline

Klik **💾 Simpan** → pilih lokasi → pipeline disimpan sebagai file `.json`.

Isi file JSON berisi semua node, parameter, posisi di kanvas, dan koneksi antar node:

```json
{
  "name": "Analisis Buffer Kawasan",
  "nodes": [
    { "node_type": "source", "params": { "schema": "public", "table": "kawasan_hutan" } },
    { "node_type": "geoprocess", "params": { "operation": "Buffer", "distance": 500 } },
    { "node_type": "output", "params": { "output_table": "sempadan_kawasan" } }
  ],
  "edges": [
    { "from_id": "...", "to_id": "..." }
  ]
}
```

### Buka Pipeline

Klik **📂 Buka** → pilih file `.json` → pipeline dimuat lengkap dengan semua node dan koneksinya.

### Reset Pipeline

Klik **🗑 Reset** untuk menghapus semua node dan membuat pipeline kosong baru.

---

## Contoh Pipeline

### Contoh 1: Buffer Kawasan Besar

**Tujuan:** Buat zona sempadan 500m di sekitar kawasan hutan yang luasnya > 1000 ha.

```
[📦 Source: kawasan_hutan | limit 5000]
    ↓
[🔍 Query: WHERE "luas_ha" > 1000 | ORDER BY luas_ha DESC]
    ↓
[⚙ Geoprocess: Buffer 500m → sempadan_kawasan_besar]
    ↓
[💾 Output: sempadan_kawasan_besar]
```

**Langkah:**
1. Tambah node **Data Source** → pilih layer `kawasan_hutan`
2. Tambah node **Query Filter** → isi WHERE: `"luas_ha" > 1000`
3. Tambah node **Geoprocessing** → pilih `Buffer`, Jarak `500`
4. Tambah node **Output** → isi nama: `sempadan_kawasan_besar`
5. Sambungkan: Source → Query → Geoprocess → Output
6. Klik **▶ Jalankan Pipeline**

---

### Contoh 2: Clip Pohon di dalam Kawasan

**Tujuan:** Pilih hanya pohon yang berada di dalam kawasan hutan.

```
[📦 Source: pohon | limit 10000]
    ↓
[⚙ Geoprocess: Intersect ← kawasan_hutan → pohon_dalam_kawasan]
    ↓
[💾 Output: pohon_dalam_kawasan]
```

---

### Contoh 3: Centroid Kawasan Kecil

**Tujuan:** Hitung titik pusat kawasan dengan luas < 100 ha.

```
[📦 Source: kawasan_hutan]
    ↓
[🔍 Query: WHERE "luas_ha" < 100]
    ↓
[⚙ Geoprocess: Centroid → centroid_kawasan_kecil]
    ↓
[💾 Output: centroid_kawasan_kecil]
```

---

## Tips dan Catatan

- Pipeline berjalan **secara berurutan** — output satu node menjadi konteks untuk node berikutnya
- Jika operasi Geoprocessing sudah membuat tabel output, node Output hanya mengkonfirmasi hasil tersebut
- File pipeline `.json` bisa dijadikan **template** — buka, ganti nama layer, jalankan ulang
- Pipeline yang kompleks (banyak node) tetap berjalan stabil karena urutan eksekusi dihitung otomatis
- Semua hasil geoprocessing dalam pipeline otomatis tersedia sebagai layer di **Layer Panel** setelah selesai

---

## Operasi Geoprocessing yang Tersedia

Pipeline Builder mendukung semua 23 operasi yang ada di Geoprocessing Tools:

| Kategori | Operasi |
|---|---|
| **Overlay** | Buffer, Intersect, Union, Clip, Difference, Symmetric Difference |
| **Geometri** | Centroid, Point on Surface, Convex Hull, Envelope, Simplify, Dissolve, Reproject, Voronoi, Delaunay |
| **Kalkulasi** | Hitung Luas, Hitung Panjang, Hitung Perimeter, Statistik Spasial |
| **Seleksi Spasial** | Select by Location, Select by Distance, Nearest Neighbor |
| **Gabung** | Spatial Join |

Lihat **[Panduan Geoprocessing](panduan-geoprocessing.md)** untuk penjelasan detail setiap operasi.

---

## Shortcut

| Aksi | Cara |
|---|---|
| Buka Pipeline Builder | `Ctrl + P` atau tombol 🔀 di toolbar |
| Tambah node | Klik tombol di panel kiri |
| Edit parameter node | Klik node di kanvas |
| Hapus node | Kanan-klik → Hapus Node |
| Sambungkan node | Dropdown From/To + klik Sambungkan |
| Simpan pipeline | Klik 💾 Simpan |
| Buka pipeline | Klik 📂 Buka |
| Reset pipeline | Klik 🗑 Reset |
| Jalankan | Klik ▶ Jalankan Pipeline |
