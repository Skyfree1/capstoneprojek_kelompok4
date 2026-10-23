import os
import joblib
import pandas as pd

FEATURES = ["n_prev", "ontime_rate", "avg_rating", "duration_days",
            "lead_days", "is_weekend", "category_code"]
_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
_model = None


def _load():
    global _model
    if _model is None and os.path.exists(_PATH):
        _model = joblib.load(_PATH)
    return _model


def label_from(p):
    return "rendah" if p < 0.33 else "sedang" if p < 0.66 else "tinggi"


def predict_risk(features):
    """Return (probabilitas, label). (None, None) jika model belum dilatih."""
    m = _load()
    if m is None:
        return None, None
    p = float(m.predict_proba(pd.DataFrame([features])[FEATURES])[0][1])
    return p, label_from(p)
