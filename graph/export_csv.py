import csv
import os

from graph.extract import collect_rows, expected_counts

OUT_DIR = os.path.join(os.path.dirname(__file__), "import")

FILES = {
    "pw_rt.csv": ("rt", ["rt_id"]),
    "pw_kategori.csv": ("kategori", ["nama"]),
    "pw_warga.csv": ("warga", ["warga_id", "nama", "rt_id", "reputasi", "trust_score"]),
    "pw_barang.csv": ("barang", ["barang_id", "nama", "kategori", "jumlah", "pemilik_id", "aktif"]),
    "pw_peminjaman.csv": ("peminjaman", ["peminjaman_id", "peminjam_id", "barang_id", "tgl_mulai",
                                         "tgl_jatuh_tempo", "tgl_kembali", "status", "jumlah", "telat_hari",
                                         "rating", "risiko", "label_risiko"]),
    "pw_penjaminan.csv": ("penjaminan", ["penjamin_id", "dijamin_id", "sejak"]),
    "pw_interaksi.csv": ("interaksi", ["peminjam_id", "pemilik_id", "kali"]),
}


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:.4f}"
    return v.isoformat() if hasattr(v, "isoformat") else v


def export(out_dir=OUT_DIR):
    rows = collect_rows()
    os.makedirs(out_dir, exist_ok=True)
    for fname, (key, cols) in FILES.items():
        with open(os.path.join(out_dir, fname), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows[key]:
                w.writerow([_fmt(r[c]) for c in cols])
    counts = expected_counts(rows)
    with open(os.path.join(out_dir, "EXPECTED_COUNTS.txt"), "w", encoding="utf-8") as f:
        f.write("Jumlah yang harus muncul di Neo4j setelah 01-02 (cek dengan 03_validasi.cypher)\n")
        for k, v in counts.items():
            f.write(f"{k}: {v}\n")
    return counts


if __name__ == "__main__":
    from app import app

    with app.app_context():
        c = export()
    print(f"CSV ditulis ke {OUT_DIR}")
    for k, v in c.items():
        print(f"  {k:<22} {v}")
