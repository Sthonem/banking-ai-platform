FEATURE_NAMES = [
    "amount",
    "time_since_last_txn",
    "location_change_km",
    "merchant_category_encoded",
    "device_seen_before",
    "txn_count_5min",
]


def encode_merchant_category(category: str) -> int:
    categories = ["grocery", "travel", "electronics", "cash", "fuel", "gaming", "general"]
    return categories.index(category) if category in categories else len(categories)


def explain(features: list[float], feature_names: list[str]) -> list[dict]:
    ranked = sorted(zip(feature_names, features, strict=True), key=lambda item: abs(item[1]), reverse=True)
    return [
        {"feature": name, "value": float(value), "contribution": float(abs(value))}
        for name, value in ranked[:3]
    ]


def validate_model_artifact(artifact: object) -> dict:
    if not isinstance(artifact, dict):
        raise ValueError("Fraud artifact must be a dict")
    missing_keys = {"model", "scaler", "feature_names"} - artifact.keys()
    if missing_keys:
        raise ValueError(f"Fraud artifact is missing keys: {sorted(missing_keys)}")
    if list(artifact["feature_names"]) != FEATURE_NAMES:
        raise ValueError(f"Fraud artifact feature_names must be {FEATURE_NAMES}")
    return artifact


def fallback_score(features: list[float]) -> float:
    amount, time_since_last, location_change, _merchant_category, device_seen_before, txn_count_5min = features
    return min(
        1.0,
        (amount / 5000 * 0.40)
        + (1 if time_since_last < 180 else 0) * 0.2
        + (location_change / 1000 * 0.20)
        + (1 - device_seen_before) * 0.1
        + min(txn_count_5min / 10, 1.0) * 0.1,
    )
