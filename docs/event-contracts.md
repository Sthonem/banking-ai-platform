# Event Contracts

All Kafka messages use the same envelope:

```json
{
  "event_id": "uuid",
  "event_type": "topic.name",
  "occurred_at": "2026-04-29T12:00:00Z",
  "correlation_id": "uuid-or-http-correlation-id",
  "payload": {}
}
```

Consumers treat `event_id` as the idempotency key and store processed events in `processed_events`.

## `user.registered`

Produced by `onboarding-service` after user creation.

```json
{
  "user_id": "uuid",
  "name": "Demo Customer",
  "email": "demo@example.com",
  "status": "pending"
}
```

## `document.uploaded`

Produced by `onboarding-service` after a document upload creates a pending KYC result.

```json
{
  "user_id": "uuid",
  "kyc_result_id": "uuid",
  "document_path": "/tmp/banking-ai-documents/<file>"
}
```

## `user.kyc.completed`

Produced by `kyc-ai-service` after OCR/extraction.

```json
{
  "user_id": "uuid",
  "kyc_result_id": "uuid",
  "status": "approved",
  "extracted_fields": {
    "name": "Demo Customer",
    "date_of_birth": "1990-01-01",
    "tc_no": "12345678901",
    "national_id": "12345678901",
    "confidence": 0.82
  }
}
```

## `txn.created`

Produced by `transaction-service` after transaction persistence.

```json
{
  "transaction_id": "uuid",
  "user_id": "uuid",
  "amount": 9500.0,
  "currency": "TRY",
  "merchant": "ATM Cash Advance",
  "location": "Berlin",
  "device_id": "new-device-001",
  "merchant_category": "cash",
  "created_at": "2026-04-29T12:00:00Z"
}
```

## `fraud.detected`

Produced by `fraud-ai-service` when `score >= FRAUD_THRESHOLD`.

```json
{
  "transaction_id": "uuid",
  "user_id": "uuid",
  "score": 0.91,
  "explanation": [
    {"feature": "amount", "value": 9500.0, "contribution": 9500.0},
    {"feature": "time_since_last_txn", "value": 120.0, "contribution": 120.0},
    {"feature": "device_seen_before", "value": 0.0, "contribution": 0.0}
  ]
}
```

## Failure Handling

- Consumer errors are retried with backoff.
- Exhausted messages are published to `<topic>.dlq`.
- Duplicate events are skipped per `(event_id, consumer_name)`.
