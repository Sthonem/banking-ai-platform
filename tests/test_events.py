from uuid import UUID

from banking_common.events import EventEnvelope, build_event, parse_event, UserRegisteredPayload


def test_event_envelope_roundtrip() -> None:
    raw = build_event(
        "user.registered",
        {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "status": "pending_kyc",
        },
        correlation_id="corr-1",
    )

    envelope, payload = parse_event(raw)

    assert envelope.event_type == "user.registered"
    assert envelope.correlation_id == "corr-1"
    assert isinstance(payload, UserRegisteredPayload)
    assert payload.user_id == UUID("11111111-1111-1111-1111-111111111111")


def test_parse_event_unknown_type_returns_none_payload() -> None:
    raw = EventEnvelope(event_type="unknown.event", payload={"foo": "bar"}).model_dump(mode="json")
    envelope, payload = parse_event(raw)
    assert envelope.event_type == "unknown.event"
    assert payload is None
