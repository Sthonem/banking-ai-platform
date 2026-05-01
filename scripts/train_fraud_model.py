from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


MODEL_DIR = Path("models")
MODEL_PATH = MODEL_DIR / "fraud_isolation_forest.joblib"


FEATURE_NAMES = [
    "amount",
    "time_since_last_txn",
    "location_change_km",
    "merchant_category_encoded",
    "device_seen_before",
    "txn_count_5min",
]


def generate_synthetic_data(rows: int = 5000) -> np.ndarray:
    rng = np.random.default_rng(42)
    normal = np.column_stack(
        [
            rng.gamma(2.0, 60.0, rows),           # amount
            rng.exponential(3600.0, rows),          # time_since_last_txn
            rng.normal(12.0, 20.0, rows).clip(0),  # location_change_km
            rng.integers(0, 8, rows),               # merchant_category_encoded
            rng.choice([0, 1], rows, p=[0.15, 0.85]),  # device_seen_before
            rng.integers(1, 4, rows),               # txn_count_5min (normal: 1-3)
        ]
    )
    anomalies = np.column_stack(
        [
            rng.gamma(5.0, 500.0, rows // 20),                      # amount: yüksek
            rng.exponential(120.0, rows // 20),                      # time_since_last_txn: kısa
            rng.normal(850.0, 250.0, rows // 20).clip(100),         # location_change_km: büyük
            rng.integers(0, 8, rows // 20),                          # merchant_category_encoded
            rng.choice([0, 1], rows // 20, p=[0.85, 0.15]),         # device_seen_before: yeni cihaz
            rng.integers(8, 20, rows // 20),                         # txn_count_5min: yüksek velocity
        ]
    )
    return np.vstack([normal, anomalies])


def train() -> dict:
    features = generate_synthetic_data()
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)
    model = IsolationForest(n_estimators=200, contamination=0.04, random_state=42)
    model.fit(scaled)

    MODEL_DIR.mkdir(exist_ok=True)
    artifact = {
        "model": model,
        "scaler": scaler,
        "feature_names": FEATURE_NAMES,
    }
    joblib.dump(artifact, MODEL_PATH)
    return artifact


if __name__ == "__main__":
    train()
    print(f"Saved {MODEL_PATH}")
