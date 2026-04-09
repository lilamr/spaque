# Panduan SQL Console

SQL Console adalah fitur untuk menjalankan query SQL secara bebas langsung ke database PostGIS. Cocok untuk query multi-layer, fungsi spasial kompleks, atau eksplorasi data yang tidak bisa dilakukan lewat Query Builder visual.

Buka melalui: menu **Query → SQL Console**, tombol **⌨ SQL Console** di toolbar, shortcut `Ctrl+Shift+Q`, atau tab **SQL Console** di panel bawah aplikasi.

---

## Antarmuka SQL Console

```
┌─────────────────────────────────────────────────────────┐
│  Konsol SQL  —  Query bebas ke PostGIS                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  SELECT *, ST_Area(geom::geography) / 10000 AS luas_ha  │
│  FROM public.kawasan_hutan                              │
│  WHERE luas_ha > 100                                    │
│  ORDER BY luas_ha DESC                                  │
│  LIMIT 500                                              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│  [▶ Jalankan SQL]  [🗑 Bersihkan]                       │
└─────────────────────────────────────────────────────────┘
```

- **Editor SQL** — area pengetikan query dengan placeholder contoh
- **▶ Jalankan SQL** — eksekusi query ke PostGIS
- **🗑 Bersihkan** — kosongkan editor

Hasil query ditampilkan di **tab Atribut** (data tabular). Jika query menghasilkan kolom geometri, data juga ditampilkan di **peta**.

---

## Query Dasar

### SELECT Sederhana

```sql
SELECT * FROM public.kawasan_hutan
WHERE luas > 1000
ORDER BY luas DESC
LIMIT 50
```

### Pilih Kolom Tertentu

```sql
SELECT gid, n_kh, luas, no_sk
FROM public.kawasan_hutan
WHERE n_kh = 'Hutan Lindung'
```

### Filter dengan Beberapa Kondisi

```sql
SELECT *
FROM public.pohon
WHERE jenis_pohon = 'Jati'
  AND dbh >= 30
  AND tinggi BETWEEN 10 AND 25
ORDER BY dbh DESC
```

---

## Query dengan Fungsi Spasial

### Hitung Luas dalam Hektar

```sql
SELECT
  gid,
  n_kh,
  ST_Area(geom::geography) / 10000 AS luas_ha
FROM public.kawasan_hutan
ORDER BY luas_ha DESC
```

### Hitung Panjang Sungai dalam Kilometer

```sql
SELECT
  gid,
  nama_sungai,
  ST_Length(geom::geography) / 1000 AS panjang_km
FROM public.sungai
ORDER BY panjang_km DESC
```

### Cek CRS dan Tipe Geometri

```sql
SELECT
  ST_SRID(geom)         AS srid,
  ST_GeometryType(geom) AS tipe_geometri,
  COUNT(*)              AS jumlah_fitur
FROM public.kawasan_hutan
GROUP BY srid, tipe_geometri
```

---

## Query Multi-Layer (Spatial Join)

### Pohon yang Berada di dalam Kawasan Hutan

```sql
SELECT
  p.gid,
  p.nama_ilmia,
  p.dbh,
  k.n_kh
FROM public.pohon p
JOIN public.kawasan_hutan k
  ON ST_Within(p.geom, k.geom)
WHERE k.n_kh = 'Hutan Lindung'
```

### Pohon dalam Radius 500m dari Sungai

```sql
SELECT DISTINCT p.*
FROM public.pohon p
WHERE EXISTS (
  SELECT 1 FROM public.sungai s
  WHERE ST_DWithin(p.geom::geography, s.geom::geography, 500)
)
```

### Hitung Jumlah Pohon per Kawasan

```sql
SELECT
  k.n_kh,
  k.gid AS kawasan_gid,
  COUNT(p.gid) AS jumlah_pohon
FROM public.kawasan_hutan k
LEFT JOIN public.pohon p
  ON ST_Within(p.geom, k.geom)
GROUP BY k.gid, k.n_kh
ORDER BY jumlah_pohon DESC
```

---

## Analisis Spasial Langsung

### Buffer dan Intersect dalam Satu Query

```sql
-- Lahan yang masuk dalam buffer 1 km dari jalan
SELECT l.*
FROM public.lahan l
WHERE ST_Intersects(
  l.geom,
  ST_Buffer(
    (SELECT ST_Union(geom) FROM public.jalan),
    1000
  )
)
```

### Centroid Semua Kawasan

```sql
SELECT
  gid,
  n_kh,
  ST_Centroid(geom) AS geom
FROM public.kawasan_hutan
```

> Karena hasil query ini mengandung kolom geometri (`geom`), hasilnya akan tampil di peta secara otomatis.

### Bounding Box Seluruh Dataset

```sql
SELECT ST_Extent(geom) AS bbox
FROM public.kawasan_hutan
```

### Nearest Neighbor — 3 Pohon Terdekat dari Setiap Titik Sampel

```sql
SELECT
  s.gid        AS sampel_gid,
  p.gid        AS pohon_gid,
  p.nama_ilmia,
  ST_Distance(s.geom::geography, p.geom::geography) AS jarak_m
FROM public.titik_sampel s
CROSS JOIN LATERAL (
  SELECT *
  FROM public.pohon
  ORDER BY geom <-> s.geom
  LIMIT 3
) p
ORDER BY s.gid, jarak_m
```

---

## Statistik Spasial

### Statistik Luas per Jenis Kawasan

```sql
SELECT
  n_kh,
  COUNT(*)                                        AS jumlah_poligon,
  ROUND(SUM(ST_Area(geom::geography) / 10000))    AS total_ha,
  ROUND(AVG(ST_Area(geom::geography) / 10000))    AS rata2_ha,
  ROUND(MIN(ST_Area(geom::geography) / 10000))    AS min_ha,
  ROUND(MAX(ST_Area(geom::geography) / 10000))    AS max_ha
FROM public.kawasan_hutan
GROUP BY n_kh
ORDER BY total_ha DESC
```

### Cek Geometri Tidak Valid

```sql
SELECT gid, ST_IsValidReason(geom) AS alasan
FROM public.kawasan_hutan
WHERE NOT ST_IsValid(geom)
```

### Temukan Duplikasi Geometri

```sql
SELECT a.gid, b.gid AS gid_duplikat
FROM public.kawasan_hutan a
JOIN public.kawasan_hutan b
  ON a.gid < b.gid
 AND ST_Equals(a.geom, b.geom)
```

---

## Membuat Tabel Baru dari Query

Hasil SQL Console bisa disimpan langsung ke tabel PostGIS baru menggunakan `CREATE TABLE AS`:

```sql
-- Simpan kawasan luas > 500 ha ke tabel baru
CREATE TABLE public.kawasan_besar AS
SELECT *,
  ST_Area(geom::geography) / 10000 AS luas_ha
FROM public.kawasan_hutan
WHERE ST_Area(geom::geography) / 10000 > 500;
```

Setelah dijalankan, klik **🔄 Refresh** di panel layer untuk melihat tabel baru.

> **Catatan:** Tabel yang dibuat via SQL Console perlu di-refresh manual. Untuk alur kerja yang lebih terintegrasi (hasil langsung tampil di peta dan layer panel), gunakan **Query Builder** atau **Geoprocessing Tools**.

---

## Referensi Fungsi PostGIS

### Fungsi Geometri Dasar

| Fungsi | Keterangan |
|---|---|
| `ST_Area(geom)` | Luas dalam unit CRS |
| `ST_Area(geom::geography)` | Luas dalam m² (akurat ellipsoid) |
| `ST_Length(geom::geography)` | Panjang dalam meter |
| `ST_Perimeter(geom::geography)` | Keliling dalam meter |
| `ST_Distance(a::geography, b::geography)` | Jarak antar geometri dalam meter |
| `ST_Centroid(geom)` | Titik pusat geometri |
| `ST_PointOnSurface(geom)` | Titik yang selalu dalam polygon |
| `ST_ConvexHull(geom)` | Cangkang cembung |
| `ST_Envelope(geom)` | Bounding box |
| `ST_Buffer(geom::geography, r)::geometry` | Buffer r meter |
| `ST_Simplify(geom, tol)` | Sederhanakan geometri |
| `ST_Transform(geom, srid)` | Ubah CRS |
| `ST_SRID(geom)` | Cek SRID/CRS saat ini |
| `ST_GeometryType(geom)` | Tipe geometri (POINT, POLYGON, dll.) |
| `ST_IsValid(geom)` | Cek validitas geometri (boolean) |
| `ST_IsValidReason(geom)` | Alasan geometri tidak valid |

### Fungsi Relasi Spasial

| Fungsi | Keterangan |
|---|---|
| `ST_Intersects(a, b)` | Cek apakah a dan b berpotongan |
| `ST_Within(a, b)` | Cek apakah a berada di dalam b |
| `ST_Contains(a, b)` | Cek apakah a berisi b |
| `ST_Overlaps(a, b)` | Cek apakah sebagian tumpang tindih |
| `ST_Touches(a, b)` | Cek apakah hanya menyentuh di batas |
| `ST_Equals(a, b)` | Cek apakah geometri identik |
| `ST_DWithin(a::geography, b::geography, r)` | Cek apakah jarak ≤ r meter |

### Fungsi Operasi Spasial

| Fungsi | Keterangan |
|---|---|
| `ST_Intersection(a, b)` | Area irisan dua geometri |
| `ST_Union(geom)` | Gabungkan geometri (aggregate) |
| `ST_Difference(a, b)` | Bagian a yang tidak tumpang tindih dengan b |
| `ST_SymDifference(a, b)` | Area yang hanya ada di salah satu geometri |
| `ST_Collect(geom)` | Kumpulkan menjadi GeometryCollection |
| `ST_Dump(geom)` | Pisahkan Multi menjadi geometri tunggal |
| `ST_MakeValid(geom)` | Perbaiki geometri tidak valid |

---

## Tips dan Praktik Terbaik

**Selalu gunakan LIMIT** untuk eksplorasi data besar agar tidak membebani koneksi:
```sql
SELECT * FROM public.pohon LIMIT 100
```

**Gunakan `::geography`** untuk pengukuran jarak/luas yang akurat dalam meter, terutama untuk data CRS geografis (EPSG:4326):
```sql
ST_Area(geom::geography) / 10000  -- luas dalam hektar
ST_Length(geom::geography)        -- panjang dalam meter
```

**Periksa SRID data** sebelum melakukan operasi spasial antar dua layer:
```sql
SELECT DISTINCT ST_SRID(geom) FROM public.nama_tabel
```

**Gunakan komentar** untuk mendokumentasikan query kompleks:
```sql
-- Hitung pohon per kawasan hutan
-- Sumber: inventarisasi 2024
SELECT k.n_kh, COUNT(p.gid) AS jumlah
FROM public.kawasan_hutan k
LEFT JOIN public.pohon p ON ST_Within(p.geom, k.geom)
GROUP BY k.n_kh
```

---

## Perbedaan SQL Console vs Query Builder

| Aspek | Query Builder | SQL Console |
|---|---|---|
| Kemudahan | ★★★★★ klik-pilih visual | ★★★ perlu tahu SQL |
| Fleksibilitas | ★★★ satu layer, filter atribut | ★★★★★ bebas tak terbatas |
| Multi-layer | ✗ tidak bisa | ✓ bisa JOIN antar layer |
| Fungsi spasial | ✗ hanya atribut | ✓ ST_Buffer, ST_Intersect, dll. |
| Simpan sebagai tabel | ✓ tombol simpan | Manual via CREATE TABLE AS |
| Riwayat query | ✓ otomatis | ✓ otomatis |

**Gunakan Query Builder** untuk filter atribut cepat pada satu layer.  
**Gunakan SQL Console** untuk analisis multi-layer, fungsi spasial, atau query yang tidak didukung Query Builder.

---

## Shortcut

| Aksi | Shortcut |
|---|---|
| Buka SQL Console | `Ctrl + Shift + Q` |
| Jalankan query | Klik **▶ Jalankan SQL** |
| Bersihkan editor | Klik **🗑 Bersihkan** |
| Pindah ke tab SQL Console | Klik tab **⌨ SQL Console** di panel bawah |
