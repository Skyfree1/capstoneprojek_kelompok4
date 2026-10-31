# Si-Pinjam Warga
Aplikasi peminjaman alat dan fasilitas antarwarga (RT/RW) dengan:
- **Trust Score** yang bisa dijelaskan (riwayat pinjam + penjamin),
- **prediksi risiko keterlambatan** (machine learning),
- **analitik graph Neo4j**: komunitas warga, PageRank penjaminan, rekomendasi alat, jalur kepercayaan.

Proyek Capstone Kelompok 4 (Ahmad Rizki Margisae, Muhammad Federick Arifin, Adifia Juniansyah).
Bagian graph sekaligus menjadi proyek mata kuliah Basis Data Graf, lihat [`docs/MODEL_GRAF.md`](docs/MODEL_GRAF.md).

## Arsitektur
```
Browser ──> Flask (app.py) ──> SQLite (instance/sipinjam.db)   sumber kebenaran transaksi
                │                     │
                │                     └─ graph/sync.py ──> Neo4j (+ GDS)   salinan untuk analisis keterhubungan
                └─ ml/ (Random Forest / Logistic Regression)   prediksi risiko telat saat pengajuan
```
Transaksi (pinjam, setujui, kembalikan) tetap di database relasional. Pertanyaan tentang
**hubungan** (siapa terhubung dengan siapa, kelompok warga, alat yang sering dipinjam bersama)
dijawab di Neo4j. Ini pola *hybrid* seperti yang dibahas di materi BDG Pertemuan 3.

## Cara menjalankan
```
python -m venv venv
venv\Scripts\activate              # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python -m ml.generate_data         # (sekali) buat data simulasi ML -> ml/data.csv
python -m ml.train                 # (sekali) latih model -> ml/model.pkl
python seed.py --reset             # (opsional) isi 45 warga demo. MENGHAPUS data lama!
python app.py                      # buka http://127.0.0.1:5000
```
Akun demo setelah seed: `warga01@demo.local` s.d. `warga45@demo.local`, kata sandi `warga123`.
Warga 01–15 = RT 01, 16–30 = RT 02, 31–45 = RT 03.

Tanpa `seed.py`, database lama tetap dipakai. Kolom baru (`rt`, `is_active`) ditambahkan
otomatis saat aplikasi start, dan akun lama mendapat RT 01.

## Menyambungkan Neo4j (fitur graph)
Aplikasi tetap berjalan tanpa Neo4j. Fitur graph aktif bila koneksi diatur.

1. **Neo4j Desktop** (disarankan, sama dengan lingkungan praktikum): buat DBMS Neo4j 5.x,
   pasang plugin **Graph Data Science** (tab *Plugins*), lalu Start.
   (Neo4j AuraDB Free juga bisa untuk query biasa, tetapi tidak menyediakan GDS,
   sehingga komunitas & PageRank tidak dihitung.)
2. Salin `.env.example` menjadi `.env` lalu isi password database. File ini dibaca otomatis.
3. Jalankan `python app.py`, buka menu **Analitik Graf**, lalu klik **Sinkronkan ke Neo4j**
   (atau dari terminal: `python -m graph.sync`).
4. Hasil sinkronisasi menampilkan validasi jumlah node/relasi (harapan vs aktual) dan ringkasan GDS.

Sinkronisasi adalah *refresh penuh*: hanya node berlabel `:PinjamWarga` yang dihapus dan dibuat
ulang, jadi data latihan lain (mis. Academic Graph P4/P5, P8) di database yang sama aman.

### Jalur LOAD CSV (untuk laporan P4)
```
python -m graph.export_csv         # tulis graph/import/pw_*.csv + EXPECTED_COUNTS.txt
```
Salin CSV ke folder *import* database Neo4j, lalu jalankan berurutan di Neo4j Browser:
`graph/cypher/00_constraints` → `01_import_nodes` → `02_import_relationships` → `03_validasi`
→ `04_query_kebutuhan_informasi` (P5) → `05_traversal_jalur` (P6) → `06_gds_analitik` (P7–P8)
→ `07_visualisasi`. `99_reset` menghapus data aplikasi saja.
CSV yang sudah ada di `graph/import/` adalah hasil `seed.py --reset`.

## Fitur
| Menu | Isi |
|---|---|
| Katalog | Cari alat + filter kategori + jumlah unit; hanya alat aktif yang tampil |
| Alat Saya | Daftar alat milik sendiri, stok, berapa kali dipinjam, ubah data/stok, aktif/nonaktifkan |
| Pinjaman Saya / Permintaan Masuk | Alur status: diajukan → disetujui → dipinjam → (terlambat) → dikembalikan |
| Warga | Daftar warga per RT dengan Trust Score |
| Profil warga | Trust Score + alasannya, penjamin, riwayat, tombol "Saya menjamin warga ini", jalur kepercayaan (Neo4j) |
| Analitik Graf | Sinkronisasi, validasi, alat terpopuler, telat per RT, PageRank, komunitas Louvain, warga terisolasi, peta jaringan |
| Ajukan pinjam | Tanggal yang sudah terpesan + rekomendasi "yang meminjam ini juga meminjam" (Jaccard, Neo4j) |

### Jumlah (stok) alat
- Saat menambah/mengubah alat, pemilik mengisi **jumlah unit** (mis. 100 gelas). Isi 1 untuk barang tunggal.
- Saat mengajukan, peminjam mengisi **jumlah yang dipinjam** (maks. stok).
- Sisa unit dihitung per tanggal: stok dikurangi unit yang sedang dipakai pada hari tersibuk dalam rentang
  tanggal yang diminta (status disetujui/dipinjam/terlambat; pinjaman terlambat dianggap masih memakai unit).
- Pengajuan yang melebihi sisa unit ditolak saat dikirim. **Persetujuan juga dicek ulang**, sehingga pemilik
  tidak bisa menyetujui bila jumlah yang diminta melebihi sisa unit (mis. dua pengajuan 70 + 50 untuk stok 100:
  yang kedua tidak bisa disetujui).
- Stok tidak bisa diturunkan di bawah jumlah unit yang sedang dipinjam/sudah disetujui.
- Pengembalian dilakukan sekaligus untuk seluruh unit dalam satu peminjaman.

### Trust Score
`Trust = 80% × reputasi + 20% × dukungan penjamin`
- **Reputasi** = 50% × (rata-rata rating / 5) + 50% × persentase tepat waktu. Pinjaman yang
  sedang terlambat dan belum kembali dihitung tidak tepat waktu. Warga baru mulai dari 50 (netral).
- **Dukungan penjamin** = jumlah penjamin dengan reputasi ≥ 70 dan tanpa pinjaman terlambat,
  penuh (100) pada 3 penjamin.
- Label: ≥ 75 tinggi, ≥ 50 sedang, < 50 rendah. Skor adalah bahan pertimbangan pemilik alat,
  bukan keputusan otomatis.

Parameter ada di `logic.py` (`TRUST_W_REPUTASI`, `PENJAMIN_MIN_REP`, dst.).

## Catatan data
`ml/data.csv` dan `seed.py` adalah **data simulasi** dengan aturan yang dinyatakan di
masing-masing file. Nyatakan ini di laporan. Nilai model dan analitik menggambarkan aturan
simulasi tersebut, bukan perilaku warga sungguhan.
