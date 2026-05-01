import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as aioredis
from fastapi import FastAPI
from sqlalchemy.orm import Session

from banking_common.config import get_settings
from banking_common.database import SessionLocal
from banking_common.events import TransactionCreatedPayload, parse_event
from banking_common.fraud import FEATURE_NAMES, encode_merchant_category, explain, fallback_score, validate_model_artifact
from banking_common.idempotency import mark_event_processed
from banking_common.kafka import KafkaPublisher, consume_forever
from banking_common.metrics import fraud_detected_total, fraud_score_histogram
from banking_common.models import FraudScore, Transaction
from banking_common.observability import configure_observability

VELOCITY_WINDOW_SECONDS = 300  # 5 dakika

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fraud-ai-service")

publisher = KafkaPublisher()
consumer_task: asyncio.Task | None = None
artifact: dict | None = None
redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global artifact, consumer_task, redis_client
    artifact = load_model()
    redis_client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    await publisher.start()
    consumer_task = asyncio.create_task(consume_forever(["txn.created"], "fraud-ai-service", handle_event))
    yield
    if consumer_task:
        consumer_task.cancel()
        await asyncio.gather(consumer_task, return_exceptions=True)
    await publisher.stop()
    await redis_client.aclose()


app = FastAPI(title="fraud-ai-service", lifespan=lifespan)
configure_observability(app, "fraud-ai-service")


def load_model() -> dict:
    model_path = Path(get_settings().fraud_model_path)
    if not model_path.exists():
        logger.warning("Fraud model missing at %s, using deterministic fallback scorer", model_path)
        return {"model": None, "scaler": None, "feature_names": FEATURE_NAMES}
    try:
        import joblib
    except ImportError:
        logger.warning("joblib is not installed; ignoring %s and using deterministic fallback scorer", model_path)
        return {"model": None, "scaler": None, "feature_names": FEATURE_NAMES}
    try:
        return validate_model_artifact(joblib.load(model_path))
    except ValueError as exc:
        raise RuntimeError(f"Invalid fraud artifact at {model_path}: {exc}") from exc


async def get_velocity_count(user_id: str) -> int:
    if redis_client is None:
        return 0
    key = f"velocity:{user_id}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, VELOCITY_WINDOW_SECONDS)
        return count
    except Exception:
        logger.warning("Redis velocity check failed for user_id=%s", user_id)
        return 0


async def derive_features(db: Session, txn: Transaction) -> list[float]:
    previous = (
        db.query(Transaction)
        .filter(Transaction.user_id == txn.user_id, Transaction.id != txn.id)
        .order_by(Transaction.created_at.desc())
        .first()
    )
    if previous:
        delta = txn.created_at - previous.created_at
        time_since_last = max(delta.total_seconds(), 1)
        device_seen_before = int(previous.device_id == txn.device_id)
        location_change = 0 if previous.location == txn.location else 650
    else:
        time_since_last = 86400
        device_seen_before = 0
        location_change = 0

    txn_count_5min = await get_velocity_count(str(txn.user_id))

    return [
        float(txn.amount),
        float(time_since_last),
        float(location_change),
        float(encode_merchant_category(txn.merchant_category)),
        float(device_seen_before),
        float(txn_count_5min),
    ]


def score_transaction(features: list[float]) -> tuple[float, list[dict]]:
    if artifact is None:
        raise RuntimeError("Fraud model artifact not loaded yet")
    if artifact.get("model") is None or artifact.get("scaler") is None:
        score = fallback_score(features)
        return round(float(score), 4), explain(features, artifact["feature_names"])
    scaled = artifact["scaler"].transform([features])
    raw = float(artifact["model"].decision_function(scaled)[0])
    score = max(0.0, min(1.0, 1 - ((raw + 0.25) / 0.5)))
    return round(score, 4), explain(features, artifact["feature_names"])


async def handle_event(topic: str, payload: dict) -> None:
    envelope, event_payload = parse_event(payload)
    if not isinstance(event_payload, TransactionCreatedPayload):
        return
    transaction_id = event_payload.transaction_id
    db: Session = SessionLocal()
    try:
        if not mark_event_processed(db, envelope.event_id, "fraud-ai-service", envelope.event_type):
            logger.info("Skipping duplicate event_id=%s", envelope.event_id)
            return
        txn = db.get(Transaction, transaction_id)
        if txn is None:
            logger.warning("Transaction not found: %s", transaction_id)
            return
        features = await derive_features(db, txn)
        score, explanation = score_transaction(features)
        is_fraud = score >= get_settings().fraud_threshold
        fraud_score = FraudScore(
            transaction_id=txn.id,
            score=score,
            is_fraud=is_fraud,
            explanation={"top_features": explanation, "scored_at": datetime.now(timezone.utc).isoformat()},
        )
        db.add(fraud_score)
        db.commit()
        fraud_score_histogram.observe(score)
    finally:
        db.close()

    if is_fraud:
        fraud_detected_total.inc()
        await publisher.publish_event(
            "fraud.detected",
            "fraud.detected",
            {
                "transaction_id": transaction_id,
                "user_id": event_payload.user_id,
                "score": score,
                "explanation": explanation,
            },
            correlation_id=envelope.correlation_id,
        )



@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "fraud-ai-service"}


@app.get("/model/status")
def model_status() -> dict[str, object]:
    loaded = artifact or {"model": None, "scaler": None, "feature_names": FEATURE_NAMES}
    return {
        "model_loaded": loaded.get("model") is not None and loaded.get("scaler") is not None,
        "model_path": get_settings().fraud_model_path,
        "feature_names": loaded.get("feature_names", FEATURE_NAMES),
    }
