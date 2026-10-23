"""Melatih & mengevaluasi model. Jalankan: python -m ml.train"""
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from ml.predict import FEATURES

df = pd.read_csv("ml/data.csv")
X, y = df[FEATURES], df["late"]
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

candidates = {
    "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000)),
    "Random Forest": RandomForestClassifier(n_estimators=200, max_depth=6, class_weight="balanced", random_state=42),
}
best_name, best_model, best_f1 = None, None, -1
for name, model in candidates.items():
    model.fit(X_tr, y_tr)
    pred = model.predict(X_te)
    f1 = f1_score(y_te, pred)
    print(f"\n=== {name} | F1 (kelas terlambat) = {f1:.3f} ===")
    print(classification_report(y_te, pred, target_names=["tepat waktu", "terlambat"]))
    if f1 > best_f1:
        best_name, best_model, best_f1 = name, model, f1

joblib.dump(best_model, "ml/model.pkl")
print(f"\nModel terbaik: {best_name} (F1={best_f1:.3f}) -> disimpan ke ml/model.pkl")
