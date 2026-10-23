# Si-Pinjam Warga
Aplikasi peminjaman alat dan fasilitas antarwarga + prediksi risiko keterlambatan (machine learning).

## Cara menjalankan
```
python -m venv venv
venv\Scripts\activate          # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python -m ml.generate_data     # buat data simulasi (ml/data.csv)
python -m ml.train             # latih model (ml/model.pkl)
python app.py                  # buka http://127.0.0.1:5000
```
Daftar dengan 2 akun (pemilik dan peminjam) untuk mencoba alur lengkap.
