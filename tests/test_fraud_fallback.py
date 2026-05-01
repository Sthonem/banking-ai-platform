import pytest

from banking_common.fraud import FEATURE_NAMES, explain, fallback_score, validate_model_artifact


def test_fallback_score_high_for_risky_transaction() -> None:
    features = [9000, 60, 900, 3, 0, 8]  # txn_count_5min=8
    score = fallback_score(features)
    explanation = explain(features, FEATURE_NAMES)

    assert score >= 0.85
    assert len(explanation) == 3


def test_validate_model_artifact_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError, match="missing keys"):
        validate_model_artifact({"model": object()})


def test_validate_model_artifact_accepts_expected_contract() -> None:
    artifact = {"model": object(), "scaler": object(), "feature_names": FEATURE_NAMES}
    assert validate_model_artifact(artifact) is artifact


def test_fallback_score_low_for_safe_transaction() -> None:
    features = [50, 86400, 0, 0, 1, 1]  # düşük tutar, uzun süre, aynı konum, tanıdık cihaz
    score = fallback_score(features)
    assert score < 0.2
