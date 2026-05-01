# Project Status

## Completed

### Infrastructure
- FastAPI microservice scaffold: api-gateway, onboarding-service, transaction-service, alert-service, kyc-ai-service, fraud-ai-service.
- Docker Compose with PostgreSQL, Kafka, Zookeeper, Redis, Prometheus, Grafana, Zipkin.
- Single shared Dockerfile (`docker/python-service.Dockerfile`) for all Python services.
- PostgreSQL schema and Alembic migration: users, kyc_results, transactions, fraud_scores, processed_events.
- `lifespan` context managers on all services (FastAPI 0.93+ pattern).

### Auth & Security
- JWT auth middleware with `require_auth` dependency.
- Document upload endpoint enforces `Bearer` token and verifies `sub == user_id`.
- Redis-backed gateway rate limiting (per IP per path, 120 req/min default).

### Kafka / Event Bus
- Typed event envelopes: `event_id`, `event_type`, `occurred_at`, `correlation_id`, `payload`.
- Consumer retry (3 attempts) + dead-letter publishing to `<topic>.dlq`.
- Idempotency via `processed_events` table (`unique event_id + consumer_name`).
- Graceful shutdown: consumer task cancellation with `asyncio.gather`.
- DLQ producer cleanup on startup failure.
- Unknown event types handled gracefully (returns `None` payload, consumer skips).

### KYC Pipeline (Faz 2)
- `POST /users` registration + `POST /users/{id}/documents` upload.
- pytesseract OCR + spaCy NER + regex extraction, deterministic fallback.
- `document.uploaded` → kyc-ai-service → `user.kyc.completed` Kafka flow.
- KYC result and user status persisted to PostgreSQL.

### Fraud Detection Pipeline (Faz 3)
- `POST /transactions` + `txn.created` → fraud-ai-service → `fraud.detected` Kafka flow.
- IsolationForest model loading with deterministic fallback scorer.
- 6-feature vector: amount, time_since_last_txn, location_change_km, merchant_category_encoded, device_seen_before, txn_count_5min.
- Redis velocity check: per-user transaction count in a 5-minute sliding window.
- Top-feature explanation (SHAP-style) saved to `fraud_scores.explanation`.
- `/model/status` endpoint.
- `scripts/train_fraud_model.py` with synthetic anomaly data (6 features).

### Observability (Faz 4)
- `prometheus-fastapi-instrumentator` on all services, `/metrics` exposed.
- Grafana dashboard provisioned from `infra/grafana/dashboards/banking-ai-overview.json`.
- OpenTelemetry + Zipkin distributed tracing on all services.
- `x-correlation-id` propagated through HTTP headers and Kafka event payloads.

### Developer Experience
- `Makefile`: `make up/down/build/logs/train/demo/test/lint/fmt`.
- `scripts/demo_flow.sh`: 6-step end-to-end flow (register → login → KYC upload → poll → transaction → poll fraud score).
- `docs/architecture.md`: full ASCII component and flow diagram.
- `docs/architecture-runbook.md`: Mermaid diagram, service responsibility table, startup order.
- CI pipeline: ruff lint + compileall + pytest + docker compose config validation.
- Unit tests: event roundtrip, unknown event type, KYC extraction, fraud fallback (high/low risk), artifact contract.

## Remaining User Actions

- Run `make train` to generate `models/fraud_isolation_forest.joblib` before the first `make demo`.
- Capture Grafana / Zipkin screenshots for portfolio presentation after `make up && make demo`.

## Known Limitations (Intentional for Portfolio Scope)

- Single PostgreSQL instance shared across all services (production would use per-service DBs).
- Alert service logs simulated notifications; no real email/SMS integration.
- KYC confidence threshold (0.67) tuned for demo reliability, not production accuracy.
- PaySim dataset not used; fraud model trains on synthetic data with realistic distributions.
