# Panduan Geoprocessing

Geoprocessing adalah fitur untuk melakukan analisis spasial menggunakan fungsi PostGIS. Tersedia di menu **Geoprocessing → Geoprocessing Tools** atau tombol **⚙ Geoprocessing** di toolbar (`Ctrl+G`).

Semua operasi menghasilkan **tabel baru** di database PostGIS dan otomatis ditampilkan di peta setelah selesai.

---

## Catatan Penting tentang Satuan

Spaque secara otomatis mendeteksi sistem koordinat (CRS) layer:

- **CRS Geografis** (EPSG:4326, DGN95, dll.) — data dalam **derajat** → Spaque otomatis konversi ke **meter** menggunakan cast `::geography`
- **CRS Proyeksi** (UTM, dll.) — data sudah dalam **meter** → digunakan langsung

Artinya: ketika Anda input jarak **500**, Spaque selalu mengartikannya sebagai **500 meter**, terlepas dari CRS layer.

---

## Kategori Operasi

### 1. Overlay

#### ⭕ Buffer
Membuat zona penyangga (buffer) di sekeliling geometri.

| Parameter | Keterangan |
|---|---|
| Layer Input | Layer yang di-buffer |
| Jarak | Radius buffer dalam **meter** |
| Segmen Busur | Jumlah segmen lingkaran (default 16, lebih tinggi = lebih halus) |
| Dissolve | Gabungkan semua hasil buffer menjadi satu geometri |

**Contoh penggunaan:**
- Buffer 500 meter di sekitar titik pohon
- Buffer 1000 meter di sekitar sungai (sempadan sungai)
- Buffer 50 meter di sekitar jalan (ROW)

---

#### ⊗ Intersect
Mengambil area irisan (tumpang tindih) antara dua layer. Hasilnya membawa atribut dari **kedua** layer.

| Parameter | Keterangan |
|---|---|
| Layer Input | Layer pertama |
| Layer Overlay | Layer kedua yang menjadi pemotong |

**Contoh penggunaan:**
- Kawasan hutan yang berada di dalam DAS tertentu
- Lahan pertanian yang masuk zona rawan banjir

---

#### ✂ Clip
Memotong layer input menggunakan batas layer clipper. Mirip Intersect, tapi hanya membawa atribut dari **layer input saja**.

| Parameter | Keterangan |
|---|---|
| Layer Input | Layer yang akan dipotong |
| Layer Clipper | Layer yang menjadi batas pemotongan |

**Perbedaan Clip vs Intersect:**
- **Clip** → hanya atribut layer input
- **Intersect** → atribut dari kedua layer

---

#### ⊕ Union
Menggabungkan semua geometri dalam satu layer menjadi satu kesatuan.

| Parameter | Keterangan |
|---|---|
| Layer Input | Layer yang digabungkan |
| Gabung berdasarkan | Field atribut untuk pengelompokan (opsional) |

---

#### ⊖ Difference
Mengambil bagian layer input yang **tidak** tumpang tindih dengan layer penghapus.

**Contoh:** Lahan tersedia = Total lahan MINUS kawasan hutan

---

#### △ Symmetric Difference
Mengambil area yang ada di salah satu layer tetapi tidak di keduanya (kebalikan dari Intersect).

---

### 2. Geometri

#### ⊙ Centroid
Menghitung titik pusat geometri setiap fitur.

> **Perhatian:** Untuk polygon konkaf (berbentuk U, tapal kuda, dll.), centroid bisa jatuh di luar polygon. Gunakan **Point on Surface** sebagai alternatif.

---

#### 📌 Point on Surface
Menghasilkan titik yang **dijamin berada di dalam** polygon. Lebih aman dari Centroid untuk polygon kompleks.

---

#### 🔷 Convex Hull
Membuat cangkang cembung (convex hull) — polygon terkecil yang melingkupi semua titik geometri.

---

#### ⬜ Envelope
Membuat bounding box (kotak pembatas) setiap fitur.

---

#### 〰 Simplify
Menyederhanakan geometri untuk mengurangi jumlah titik.

| Parameter | Keterangan |
|---|---|
| Toleransi | Jarak maksimum penyimpangan dalam unit CRS layer |
| Pertahankan Topologi | Mencegah self-intersection pada hasil |

> **Pedoman toleransi:**
> - EPSG:4326: `0.001` ≈ 111 meter
> - EPSG:32750 (UTM): `1.0` = 1 meter, `10.0` = 10 meter

---

#### 🫧 Dissolve
Menggabungkan geometri berdasarkan nilai atribut yang sama.

**Contoh:** Dissolve kawasan hutan berdasarkan `n_kh` → setiap jenis kawasan digabung menjadi satu polygon.

---

#### 🌐 Reproject
Mengubah sistem koordinat (CRS) layer ke CRS target.

| CRS Tersedia | EPSG |
|---|---|
| WGS 84 | 4326 |
| Web Mercator | 3857 |
| UTM Zone 47-51 S/N | 32747-32751, 32647-32648 |
| DGN95 | 4755 |

---

#### 🕸 Voronoi
Membuat diagram Voronoi dari sekumpulan titik. Setiap sel Voronoi mencakup semua area yang lebih dekat ke titik tersebut dibanding titik lain.

**Syarat:** Layer input harus bertipe **Point**.

---

#### ◬ Delaunay
Triangulasi Delaunay dari sekumpulan titik. Menghasilkan jaringan segitiga optimal.

**Syarat:** Layer input harus bertipe **Point**.

---

### 3. Kalkulasi

#### 📐 Hitung Luas
Menambahkan kolom luas area. Akurat menggunakan ellipsoid WGS84 (bukan Web Mercator).

| Satuan | Kolom Hasil |
|---|---|
| m² | `area_m2` |
| ha | `area_ha` |
| km² | `area_km2` |

---

#### 📏 Hitung Panjang
Menambahkan kolom panjang geometri dalam meter. Cocok untuk layer **LineString**.

---

#### 🔲 Hitung Perimeter
Menambahkan kolom keliling geometri dalam meter. Cocok untuk layer **Polygon**.

---

#### 📊 Statistik Spasial
Menghitung statistik atribut numerik (COUNT, SUM, AVG, MIN, MAX, STDDEV) per kelompok.

| Parameter | Keterangan |
|---|---|
| Kolom Nilai | Kolom numerik yang dihitung statistiknya |
| Kolom Grup | Kolom untuk pengelompokan (opsional) |

---

### 4. Seleksi Spasial

#### 📍 Select by Location
Memilih fitur berdasarkan relasi spasial dengan layer lain.

| Predikat | Keterangan |
|---|---|
| ST_Intersects | Saling bersentuhan atau tumpang tindih |
| ST_Contains | Layer A berisi seluruh layer B |
| ST_Within | Layer A berada sepenuhnya di dalam layer B |
| ST_Overlaps | Sebagian tumpang tindih |
| ST_Touches | Hanya menyentuh di batas |
| ST_Crosses | Saling memotong |
| ST_Covers | Layer A mencakup seluruh layer B |

---

#### 📡 Select by Distance
Memilih fitur dalam radius jarak tertentu dari layer referensi.

| Parameter | Keterangan |
|---|---|
| Jarak | Radius pencarian dalam **meter** |

---

#### 🎯 Nearest Neighbor
Mencari K fitur terdekat dari setiap fitur layer input.

| Parameter | Keterangan |
|---|---|
| K Tetangga | Jumlah tetangga terdekat yang dicari |

Hasilnya menyertakan kolom `dist_m` berisi jarak dalam meter.

---

### 5. Gabung

#### 🔗 Spatial Join
Menggabungkan atribut dua layer berdasarkan relasi spasial.

| Parameter | Keterangan |
|---|---|
| Layer Input | Layer utama |
| Layer Join | Layer yang atributnya digabungkan |
| Tipe Join | INNER (hanya yang match) / LEFT OUTER (semua dari input) |
| Predikat | Relasi spasial yang digunakan |

---

## Alur Kerja Umum

### Contoh: Analisis Pohon dalam Kawasan Hutan

```
1. Import layer pohon (titik) dan kawasan_hutan (polygon)
2. Geoprocessing → Select by Location
   - Layer Input: pohon
   - Layer Referensi: kawasan_hutan
   - Predikat: ST_Within
   → Hasil: titik pohon yang berada di dalam kawasan hutan

3. Geoprocessing → Hitung Luas
   - Layer Input: kawasan_hutan
   - Satuan: ha
   → Hasil: kawasan_hutan + kolom area_ha

4. Query Builder → filter kawasan dengan luas > 1000 ha
```

---

### Contoh: Buffer dan Clip

```
1. Geoprocessing → Buffer
   - Layer Input: sungai (linestring)
   - Jarak: 100 meter
   → Hasil: sempadan_sungai (polygon 100m kiri-kanan sungai)

2. Geoprocessing → Clip
   - Layer Input: lahan_pertanian
   - Layer Clipper: sempadan_sungai
   → Hasil: lahan pertanian dalam sempadan sungai
     (tidak boleh ada aktivitas pertanian di sini)
```

---

## Tips dan Catatan

- Hasil geoprocessing selalu disimpan di schema `public` dengan nama yang bisa diubah
- Nama tabel output tidak boleh mengandung spasi (otomatis dikonversi ke underscore)
- Jika nama tabel sudah ada, tabel lama akan di-DROP dan diganti
- Klik **👁 Preview SQL** untuk melihat SQL yang akan dijalankan sebelum eksekusi
- Semua hasil otomatis muncul di Layer Panel setelah selesai

---

## Shortcut

| Aksi | Shortcut |
|---|---|
| Buka Geoprocessing | `Ctrl + G` |
| Buffer | Toolbar ⭕ Buffer |
| Intersect | Toolbar ⊗ Intersect |
| Clip | Toolbar ✂ Clip |
| Union | Toolbar ⊕ Union |
| Centroid | Toolbar ⊙ Centroid |
