# Panduan Query Builder Visual

Query Builder adalah fitur untuk membangun query atribut secara visual tanpa perlu menulis SQL secara manual. Tersedia di menu **Query → Query Builder** atau tombol **🔍 Query Builder** di toolbar.

---

## Antarmuka Query Builder

```
┌─────────────────────────────────────────────────────────────┐
│  🔍  Query Builder Visual                                    │
├─────────────────────────────────────────────────────────────┤
│  Layer / Tabel:  [ public.kawasan_hutan          ▼ ]        │
├─────────────────────────────────────────────────────────────┤
│  Kondisi Filter (WHERE)                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  [ n_kh      ▼ ] [ =   ▼ ] [ Hutan Lindung ]  [✕] │   │
│  │  [ AND ▼ ] [ luas ▼ ] [ >= ▼ ] [ 1000 ]       [✕] │   │
│  └─────────────────────────────────────────────────────┘   │
│  [ ＋ Tambah Kondisi ]  [ 🗑 Reset ]                        │
├─────────────────────────────────────────────────────────────┤
│  Urutkan: [ luas          ▼ ] [ DESC ▼ ]  Limit: [ 100 ]  │
├─────────────────────────────────────────────────────────────┤
│  Preview SQL                                                 │
│  SELECT *                                                    │
│  FROM "public"."kawasan_hutan"                              │
│  WHERE "n_kh" = 'Hutan Lindung'                             │
│    AND "luas" >= 1000                                        │
│  ORDER BY "luas" DESC                                        │
│  LIMIT 100                                                   │
├─────────────────────────────────────────────────────────────┤
│  [ Batal ]  [ 🗑 Reset ]  [ 👁 Preview ]  [ ▶ Jalankan ]  │
└─────────────────────────────────────────────────────────────┘
```

---

## Langkah Penggunaan

### 1. Pilih Layer
Pilih layer/tabel yang ingin di-query dari dropdown **Layer / Tabel**. Daftar otomatis terisi dari layer yang tersedia di database.

### 2. Tambah Kondisi Filter
Klik **＋ Tambah Kondisi** untuk menambah baris filter.

Setiap baris kondisi terdiri dari:
- **Logika** (AND / OR) — menghubungkan kondisi satu dengan berikutnya
- **Kolom** — nama kolom yang difilter
- **Operator** — cara perbandingan nilai
- **Nilai** — nilai yang digunakan sebagai filter

### 3. Pilih Operator

| Operator | Keterangan | Contoh Nilai |
|---|---|---|
| `=` | Sama dengan | `Hutan Lindung` |
| `≠` | Tidak sama dengan | `Hutan Produksi` |
| `>` | Lebih besar | `1000` |
| `≥` | Lebih besar atau sama | `500` |
| `<` | Lebih kecil | `100` |
| `≤` | Lebih kecil atau sama | `250` |
| `LIKE` | Mengandung pola (case-sensitive) | `%Rinjani%` |
| `ILIKE` | Mengandung pola (tidak case-sensitive) | `%hutan%` |
| `IS NULL` | Nilai kosong | *(tidak perlu isi nilai)* |
| `IS NOT NULL` | Nilai tidak kosong | *(tidak perlu isi nilai)* |
| `IN` | Termasuk dalam daftar | `'HL','HPT','HP'` |
| `NOT IN` | Tidak termasuk dalam daftar | `'APL','Lainnya'` |
| `BETWEEN` | Di antara dua nilai | `100, 500` |

> **Tips LIKE/ILIKE:** Gunakan `%` sebagai wildcard.
> - `%Rinjani%` → mengandung kata "Rinjani" di mana saja
> - `KH.%` → dimulai dengan "KH."
> - `%Lindung` → diakhiri dengan "Lindung"

> **Tips IN/NOT IN:** Pisahkan nilai dengan koma dan beri tanda kutip untuk teks.
> Contoh: `'HL','HPT','HP'`

> **Tips BETWEEN:** Pisahkan dua nilai dengan koma.
> Contoh: `1000, 5000`

### 4. Kombinasi AND / OR
- **AND** — kedua kondisi harus terpenuhi
- **OR** — salah satu kondisi cukup terpenuhi

Contoh:
```
luas >= 1000  AND  n_kh = 'Hutan Lindung'
→ Kawasan dengan luas ≥ 1000 DAN jenisnya Hutan Lindung

luas >= 5000  OR  luas <= 100
→ Kawasan dengan luas sangat besar ATAU sangat kecil
```

### 5. Pengurutan (ORDER BY)
Pilih kolom untuk mengurutkan hasil dan arah pengurutan:
- **ASC** — dari kecil ke besar / A ke Z
- **DESC** — dari besar ke kecil / Z ke A

### 6. Limit
Batasi jumlah baris yang ditampilkan. Kosongkan (nilai 0) untuk menampilkan semua data.

### 7. Preview SQL
Panel bawah menampilkan SQL yang akan dijalankan secara otomatis saat kondisi berubah. Ini membantu memahami query yang terbentuk.

### 8. Jalankan
Klik **▶ Jalankan Query** untuk menjalankan query. Hasilnya:
- Ditampilkan di **tabel atribut** (tab Atribut)
- Ditampilkan di **peta** jika query menghasilkan data geometri

---

## Keterbatasan Query Builder

- Hanya mendukung **satu layer** per query
- Tidak mendukung fungsi spasial (gunakan **SQL Console** untuk query spasial multi-layer)
- Kolom yang dipilih selalu `SELECT *` (semua kolom)

## Query Multi-Layer

Untuk query yang melibatkan lebih dari satu layer atau menggunakan fungsi spasial, gunakan **SQL Console** (menu Query → SQL Console atau Ctrl+Shift+Q):

```sql
SELECT a.n_kh, b.nama_desa, ST_Intersection(a.geom, b.geom) AS geom
FROM public.kawasan_hutan a
JOIN public.batas_desa b ON ST_Intersects(a.geom, b.geom)
WHERE a.n_kh = 'Hutan Lindung'
```

---

## Shortcut

| Aksi | Shortcut |
|---|---|
| Buka Query Builder | `Ctrl + Q` |
| Buka SQL Console | `Ctrl + Shift + Q` |
