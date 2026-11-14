import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from banking_common.events import FraudDetectedPayload, KycCompletedPayload, parse_event
from banking_common.kafka import consume_forever
from banking_common.observability import configure_observability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alert-service")

consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task
    consumer_task = asyncio.create_task(
        consume_forever(["fraud.detected", "user.kyc.completed"], "alert-service", handle_event)
    )
    yield
    if consumer_task:
        consumer_task.cancel()
        await asyncio.gather(consumer_task, return_exceptions=True)


app = FastAPI(title="alert-service", lifespan=lifespan)
configure_observability(app, "alert-service")


async def handle_event(topic: str, payload: dict) -> None:
    envelope, event_payload = parse_event(payload)
    if isinstance(event_payload, FraudDetectedPayload):
        logger.warning(
            "SIMULATED ALERT fraud correlation_id=%s transaction_id=%s score=%s user_id=%s",
            envelope.correlation_id,
            event_payload.transaction_id,
            event_payload.score,
            event_payload.user_id,
        )
    elif isinstance(event_payload, KycCompletedPayload):
        logger.info(
            "SIMULATED NOTIFICATION kyc correlation_id=%s user_id=%s status=%s",
            envelope.correlation_id,
            event_payload.user_id,
            event_payload.status,
        )



@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "alert-service"}
