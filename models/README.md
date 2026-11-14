# Model Artifacts

Put the trained fraud artifact here:

```text
models/fraud_isolation_forest.joblib
```

The fraud service expects a `joblib` artifact shaped like:

```python
{
    "model": isolation_forest_model,
    "scaler": fitted_standard_scaler,
    "feature_names": [
        "amount",
        "time_since_last_txn",
        "location_change_km",
        "merchant_category_encoded",
        "device_seen_before",
        "txn_count_5min",
    ],
}
```

If the file is missing, the service uses the deterministic fallback scorer so the rest of the platform can still run.
