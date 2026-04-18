# Panduan Tabel Atribut

Tabel Atribut adalah fitur untuk melihat, mengedit, dan mengelola data atribut layer — baik layer spasial (polygon, garis, titik) maupun tabel non-spasial (CSV/tabel biasa tanpa geometri).

Buka melalui:
- **Double-klik** layer di Layer Panel → tab **📋 Atribut** di panel bawah
- Klik **↗ Window** di toolbar panel atribut → buka sebagai jendela popup terpisah
- **Klik kanan** layer di Layer Panel → **Lihat Atribut**

---

## Dua Mode Tampilan

### 1. Panel Bawah (Docked)
Tabel atribut muncul di panel bawah aplikasi, menyatu dengan SQL Console dan Log. Cocok untuk lihat data cepat.

### 2. Popup Window (Terpisah)
Klik **↗ Window** untuk membuka tabel atribut di jendela tersendiri. Bisa dibuka beberapa sekaligus untuk membandingkan layer yang berbeda.

Fitur tambahan di popup window:
- **Paginasi** — navigasi per 5.000 baris untuk data besar
- **Scroll horizontal** — lihat semua kolom tanpa terpotong
- **Refresh otomatis** — setelah tambah/hapus kolom, data langsung diperbarui

---

## Tampilan Tabel

```
┌────────────────────────────────────────────────────────────────────┐
│  14 fitur  [Kolom Geom]  ⚠ Tidak ada PK     [Tambah Baris] ...    │
├────────────────────────────────────────────────────────────────────┤
│  ✏ Mode Edit Aktif — Double-klik sel untuk mengedit               │
├───────────┬───────────┬───────────┬──────────┬────────────────────┤
│ gid       │ nama      │ luas_ha   │ jenis    │ catatan            │
├───────────┼───────────┼───────────┼──────────┼────────────────────┤
│ 1         │ Kawasan A │ 1234.56   │ HL       │                    │
│ 2         │ Kawasan B │ 567.89    │ HPT      │ revisi 2024        │
├────────────────────────────────────────────────────────────────────┤
│  ◀ Sebelumnya    Hal. 1 / 3  (baris 1–5000 dari 12450)  Berikutnya ▶ │
└────────────────────────────────────────────────────────────────────┘
```

### Kolom-kolom Toolbar

| Elemen | Keterangan |
|---|---|
| **N fitur** | Jumlah total baris dalam tabel |
| **[Kolom Geom]** | Checkbox untuk menampilkan/menyembunyikan kolom geometri |
| **⚠ Tidak ada PK** | Peringatan bahwa tabel tidak punya Primary Key — edit tidak tersedia |
| **✏ Edit** | Aktifkan mode edit (hanya muncul jika tabel punya PK) |
| **➕ Tambah Baris** | Tambah baris baru (hanya untuk tabel non-spasial) |
| **💾 Simpan** | Simpan semua perubahan ke database |
| **✕ Batal** | Batalkan semua perubahan yang belum disimpan |

---

## Primary Key (PK)

Primary Key adalah kolom yang mengidentifikasi setiap baris secara unik. Spaque memerlukan PK untuk:
- Edit nilai atribut
- Hapus baris
- Simpan perubahan ke database

### Deteksi PK Otomatis
Spaque mendeteksi PK melalui:
1. Query `information_schema` PostgreSQL untuk membaca constraint PRIMARY KEY aktual
2. Fallback heuristik berdasarkan nama kolom: `gid`, `id`, `fid`, `ogc_fid`, `objectid`, `_gid`, dll.

### Tabel Tanpa PK
Jika tabel tidak memiliki PK:
- Muncul peringatan **⚠ Tidak ada PK — edit tidak tersedia** di toolbar
- Tombol **✏ Edit** disembunyikan
- Data tetap bisa dilihat dan di-export

**Cara menambahkan PK:**

```sql
-- Tambah kolom _gid sebagai SERIAL PRIMARY KEY
ALTER TABLE public.nama_tabel
ADD COLUMN _gid SERIAL PRIMARY KEY;
```

Atau saat import file: pilih opsi **"Buat otomatis (_gid)"** di bagian ④ Primary Key dialog Import.

---

## Edit Atribut

### Syarat
- Tabel harus memiliki Primary Key
- Koneksi database aktif

### Langkah Edit
1. Klik **✏ Edit** — mode edit aktif, banner hijau muncul
2. **Double-klik** sel yang ingin diubah
3. Ketik nilai baru → tekan Enter atau klik sel lain
4. Klik **💾 Simpan** untuk menyimpan ke database
5. Atau klik **✕ Batal** untuk membatalkan semua perubahan

### Perilaku Edit
- Sel yang diubah disorot warna kuning
- Kolom PK dan kolom geometri tidak bisa diubah (terlindungi otomatis)
- Semua perubahan disimpan sekaligus saat klik Simpan
- Perubahan dikirim ke database via `UPDATE ... WHERE pk_col = nilai`

### Edit Lintas Halaman (Popup Window)
Di popup window dengan paginasi, perubahan di halaman mana pun tersimpan dalam memori hingga klik Simpan. Nomor baris global dihitung otomatis: `halaman × 5000 + baris_lokal`.

---

## Tambah & Hapus Kolom

### Tambah Kolom
Klik **➕ Kolom** saat mode edit aktif. Dialog muncul dengan dua field:

| Field | Keterangan |
|---|---|
| **Nama Kolom** | Huruf, angka, underscore saja (tanpa spasi) |
| **Tipe Data** | Pilih dari dropdown |

**Tipe data tersedia:**

| Tipe | Keterangan |
|---|---|
| TEXT | Teks bebas panjang |
| INTEGER | Bilangan bulat |
| DOUBLE PRECISION | Bilangan desimal |
| BOOLEAN | true / false |
| DATE | Tanggal (YYYY-MM-DD) |
| TIMESTAMP | Tanggal dan waktu |
| NUMERIC | Angka presisi tinggi |
| VARCHAR(255) | Teks maks 255 karakter |
| BIGINT | Bilangan bulat sangat besar |

Kolom baru dibuat via `ALTER TABLE ... ADD COLUMN`. Popup window direfresh otomatis.

### Hapus Kolom
Klik **➖ Kolom** saat mode edit aktif → pilih kolom dari dropdown → konfirmasi. Operasi menggunakan `ALTER TABLE ... DROP COLUMN`. **Tidak bisa dibatalkan.**

> Kolom PK dan kolom geometri tidak bisa dihapus melalui antarmuka ini.

---

## Hapus Baris

1. Aktifkan mode edit
2. Klik baris yang ingin dihapus (pilih satu baris)
3. Klik **🗑 Hapus Baris** → konfirmasi
4. Baris dihapus permanen via `DELETE FROM ... WHERE pk_col = nilai`

> Hapus baris memerlukan PK. Jika tidak ada PK, tombol Hapus Baris tidak aktif.

---

## Tabel Non-Spasial

Tabel non-spasial adalah tabel PostgreSQL biasa tanpa kolom geometri — hasil import CSV tanpa koordinat, atau tabel referensi manual.

### Perbedaan dengan Tabel Spasial

| Fitur | Spasial | Non-Spasial |
|---|---|---|
| Tampil di Layer Panel | ✓ (ikon 🔷/〰/📍) | ✓ (ikon 📋) |
| Tampil di Peta | ✓ | ✗ |
| Edit Atribut | ✓ (perlu PK) | ✓ (perlu PK) |
| Tambah Baris | ✗ | ✓ (perlu PK) |
| Tambah/Hapus Kolom | ✓ | ✓ |
| Export | ✓ (GeoJSON/SHP/CSV) | ✓ (CSV saja) |
| Kolom Geometri | Ada | Tidak ada |

### Tambah Baris (Non-Spasial)
Tombol **➕ Tambah Baris** muncul otomatis untuk tabel non-spasial yang memiliki PK. Klik tombol → dialog isian muncul dengan field untuk setiap kolom:

- Kolom PK diisi otomatis oleh database (SERIAL/auto-increment)
- Nilai kosong otomatis disimpan sebagai NULL
- Maksimum 20 kolom ditampilkan dalam dialog (kolom selebihnya bisa diisi setelah baris dibuat)

### Import CSV sebagai Non-Spasial
Di dialog Import, pilih file CSV lalu centang **"Import sebagai tabel atribut biasa (tanpa geometri)"**. Field lon/lat disembunyikan otomatis. Data disimpan via `pandas.to_sql()`.

Untuk PK, pilih strategi di bagian ④ Primary Key:
- **Buat otomatis (_gid)** — tambah `_gid SERIAL PRIMARY KEY` (direkomendasikan)
- **Pilih kolom existing** — jadikan kolom yang ada sebagai PK
- **Tanpa PK** — tidak buat PK (edit tidak tersedia)

---

## Paginasi (Popup Window)

Popup window membagi data menjadi halaman 5.000 baris per halaman.

```
◀ Sebelumnya    Hal. 2 / 5  (baris 5001–10000 dari 24312)    Berikutnya ▶
```

- Navigasi dengan tombol **◀ Sebelumnya** dan **Berikutnya ▶**
- Perubahan di semua halaman dikumpulkan di memori, disimpan sekaligus saat klik Simpan
- Filter dan sort bekerja hanya pada halaman aktif

---

## Scroll & Resize Kolom

- **Scroll horizontal** — tersedia saat kolom melebihi lebar jendela
- **Scroll vertikal** — tersedia saat baris melebihi tinggi jendela
- Lebar kolom disesuaikan otomatis dengan konten (`ResizeToContents`)
- Klik header kolom untuk mengurutkan (sort) secara ascending/descending

---

## Shortcut

| Aksi | Cara |
|---|---|
| Buka tabel atribut | Double-klik layer di Layer Panel |
| Buka sebagai popup window | Klik **↗ Window** di toolbar |
| Aktifkan mode edit | Klik **✏ Edit** |
| Edit sel | Double-klik sel |
| Simpan perubahan | Klik **💾 Simpan** |
| Batalkan perubahan | Klik **✕ Batal** |
| Hapus baris terpilih | Klik **🗑 Hapus Baris** |
| Tambah kolom | Klik **➕ Kolom** (mode edit) |
| Hapus kolom | Klik **➖ Kolom** (mode edit) |
| Tambah baris | Klik **➕ Tambah Baris** (non-spasial) |
| Pindah halaman | Klik **◀** / **▶** di paginasi bar |
| Tampilkan kolom geom | Centang **Kolom Geom** |
