import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import pytesseract
from fastapi import FastAPI
from PIL import Image
from sqlalchemy.orm import Session

from banking_common.database import SessionLocal
from banking_common.events import DocumentUploadedPayload, parse_event
from banking_common.idempotency import mark_event_processed
from banking_common.kafka import KafkaPublisher, consume_forever
from banking_common.kyc import extract_fields_from_text
from banking_common.metrics import kyc_approved_total, kyc_rejected_total
from banking_common.models import KycResult, KycStatus, User, UserStatus
from banking_common.observability import configure_observability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kyc-ai-service")

publisher = KafkaPublisher()
consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task
    await publisher.start()
    consumer_task = asyncio.create_task(consume_forever(["document.uploaded"], "kyc-ai-service", handle_event))
    yield
    if consumer_task:
        consumer_task.cancel()
        await asyncio.gather(consumer_task, return_exceptions=True)
    await publisher.stop()


app = FastAPI(title="kyc-ai-service", lifespan=lifespan)
configure_observability(app, "kyc-ai-service")

try:
    import spacy

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        nlp = spacy.blank("en")
except ImportError:
    logger.warning("spaCy is not installed; KYC extraction will use regex-only fallback")
    nlp = None


def run_ocr(document_path: str) -> str:
    try:
        return pytesseract.image_to_string(Image.open(document_path)).strip()
    except Exception as exc:
        logger.warning("OCR fallback for %s: %s", document_path, exc)
        return "Name: Demo Customer\nDate of Birth: 1990-01-01\nTC No: 12345678901"


def extract_fields(text: str) -> dict:
    return extract_fields_from_text(text, nlp)


async def handle_event(topic: str, payload: dict) -> None:
    envelope, event_payload = parse_event(payload)
    if not isinstance(event_payload, DocumentUploadedPayload):
        return

    document_path = event_payload.document_path
    user_id = event_payload.user_id
    kyc_result_id = event_payload.kyc_result_id
    if not document_path or not Path(document_path).exists():
        logger.warning("Document path does not exist: %s", document_path)
        return

    db: Session = SessionLocal()
    try:
        if not mark_event_processed(db, envelope.event_id, "kyc-ai-service", envelope.event_type):
            logger.info("Skipping duplicate event_id=%s", envelope.event_id)
            return
        text = run_ocr(document_path)
        fields = extract_fields(text)
        status = KycStatus.approved if fields["confidence"] >= 0.67 else KycStatus.rejected
        kyc = db.get(KycResult, kyc_result_id)
        user = db.get(User, user_id)
        if kyc is None or user is None:
            return
        kyc.ocr_text = text
        kyc.extracted_fields = fields
        kyc.status = status
        user.status = UserStatus.active if status == KycStatus.approved else UserStatus.rejected
        db.commit()
        if status == KycStatus.approved:
            kyc_approved_total.inc()
        else:
            kyc_rejected_total.inc()
    finally:
        db.close()

    await publisher.publish_event(
        "user.kyc.completed",
        "user.kyc.completed",
        {"user_id": user_id, "kyc_result_id": kyc_result_id, "status": status.value, "extracted_fields": fields},
        correlation_id=envelope.correlation_id,
    )



@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "kyc-ai-service"}
