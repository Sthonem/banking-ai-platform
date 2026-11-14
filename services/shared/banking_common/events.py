import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EventEnvelope(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payload: dict[str, Any]


class UserRegisteredPayload(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    status: str


class DocumentUploadedPayload(BaseModel):
    user_id: uuid.UUID
    kyc_result_id: uuid.UUID
    document_path: str


class KycCompletedPayload(BaseModel):
    user_id: uuid.UUID
    kyc_result_id: uuid.UUID
    status: Literal["pending", "approved", "rejected"]
    extracted_fields: dict[str, Any]


class TransactionCreatedPayload(BaseModel):
    transaction_id: uuid.UUID
    user_id: uuid.UUID
    amount: float
    currency: str
    merchant: str
    location: str
    device_id: str
    merchant_category: str
    created_at: datetime

    model_config = ConfigDict(arbitrary_types_allowed=True)


class FraudDetectedPayload(BaseModel):
    transaction_id: uuid.UUID
    user_id: uuid.UUID | None = None
    score: float
    explanation: list[dict[str, Any]]


EVENT_PAYLOADS: dict[str, type[BaseModel]] = {
    "user.registered": UserRegisteredPayload,
    "document.uploaded": DocumentUploadedPayload,
    "user.kyc.completed": KycCompletedPayload,
    "txn.created": TransactionCreatedPayload,
    "fraud.detected": FraudDetectedPayload,
}


def build_event(
    event_type: str, payload: BaseModel | dict[str, Any], correlation_id: str | None = None
) -> dict[str, Any]:
    payload_model = EVENT_PAYLOADS[event_type]
    validated = payload if isinstance(payload, BaseModel) else payload_model.model_validate(payload)
    return EventEnvelope(
        event_type=event_type,
        correlation_id=correlation_id or str(uuid.uuid4()),
        payload=validated.model_dump(mode="json"),
    ).model_dump(mode="json")


def parse_event(raw: dict[str, Any]) -> tuple[EventEnvelope, BaseModel | None]:
    envelope = EventEnvelope.model_validate(raw)
    payload_model = EVENT_PAYLOADS.get(envelope.event_type)
    if payload_model is None:
        return envelope, None
    return envelope, payload_model.model_validate(envelope.payload)
