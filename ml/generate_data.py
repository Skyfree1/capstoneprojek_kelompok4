"""Membuat DATA SIMULASI riwayat peminjaman. Jalankan: python -m ml.generate_data"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
N = 1500

n_prev = rng.integers(0, 15, N)
ontime = np.where(n_prev == 0, 0.5, rng.beta(5, 2, N))
rating = np.where(n_prev == 0, 3.0, np.clip(rng.normal(4.0 * ontime + 1.0, 0.6), 1, 5))
duration = rng.integers(1, 15, N)
lead = rng.integers(0, 21, N)
weekend = rng.integers(0, 2, N)
cat = rng.integers(0, 4, N)

# Aturan peluang terlambat/tidak kembali (asumsi simulasi, nyatakan di laporan)
p = (0.10 + 0.30 * (1 - ontime) + 0.02 * np.maximum(duration - 3, 0)
     - 0.04 * (rating - 3) + 0.05 * weekend + 0.03 * (cat == 0)
     + rng.normal(0, 0.05, N))
p = np.clip(p, 0.02, 0.95)
late = (rng.random(N) < p).astype(int)

pd.DataFrame({"n_prev": n_prev, "ontime_rate": ontime.round(3), "avg_rating": rating.round(2),
              "duration_days": duration, "lead_days": lead, "is_weekend": weekend,
              "category_code": cat, "late": late}).to_csv("ml/data.csv", index=False)
print("data.csv dibuat:", N, "baris | proporsi terlambat:", round(late.mean(), 3))
