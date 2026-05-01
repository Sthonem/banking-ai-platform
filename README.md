# Banking AI Mini Platform

Portfolio-grade banking microservice platform focused on enterprise integration patterns, event-driven architecture, and AI pipelines.

## Architecture

- `api-gateway`: JWT verification, Redis-backed rate limiting, downstream routing.
- `onboarding-service`: user registration, KYC document intake, `user.registered` event producer.
- `transaction-service`: transaction persistence, `txn.created` event producer.
- `alert-service`: Kafka consumer for fraud/KYC events, simulated notifications.
- `kyc-ai-service`: document OCR + NLP extraction, `user.kyc.completed` event producer.
- `fraud-ai-service`: transaction anomaly scoring, top-feature explanation, `fraud.detected` event producer.

## Event Topics

- `user.registered`
- `document.uploaded` — internal KYC document trigger
- `user.kyc.completed`
- `txn.created`
- `fraud.detected`

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

Main entrypoints:

- API Gateway: http://localhost:8080/docs
- Onboarding service: http://localhost:8001/docs
- Transaction service: http://localhost:8002/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Zipkin: http://localhost:9411

Default Grafana credentials are `admin` / `admin`.

## Demo Flow

1. Register a user through `POST /onboarding/users` on the gateway.
2. Upload a KYC document through `POST /onboarding/users/{user_id}/documents`.
3. Create a transaction through `POST /transactions`.
4. Watch Kafka-driven KYC and fraud events update the database and alert logs.

## Local Development

Create a virtualenv and install dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements/dev.txt
```

Train or refresh the fraud model:

```bash
python scripts/train_fraud_model.py
```

The application no longer auto-trains a fraud model at service startup. Put your trained artifact at
`models/fraud_isolation_forest.joblib`, or set `FRAUD_MODEL_PATH` to another path. Until then, `fraud-ai-service`
uses a deterministic fallback scorer so the platform flow remains demoable.

Docker runtime images keep heavy AI dependencies lean for fast portfolio demos. `spaCy` and `SHAP` are included in
`requirements/dev.txt` for local AI work, while the containers can run with OCR/regex KYC extraction and fraud fallback
until you provide the trained model pipeline.

Run one service locally:

```bash
PYTHONPATH=services/shared uvicorn app.main:app --app-dir services/onboarding-service --reload --port 8001
```

## API Coverage

- `POST /onboarding/users`
- `GET /onboarding/users`
- `GET /onboarding/users/{user_id}`
- `POST /onboarding/auth/login`
- `POST /onboarding/users/{user_id}/documents`
- `GET /onboarding/users/{user_id}/kyc-results`
- `GET /onboarding/kyc-results/{kyc_result_id}`
- `POST /transactions`
- `GET /transactions`
- `GET /transactions/{transaction_id}`
- `GET /transactions/{transaction_id}/fraud-scores`

## Smoke Demo

After the stack is up, run:

```bash
bash scripts/demo_flow.sh
```

The script registers a user, logs in, creates a high-risk transaction, and lets the Kafka fraud pipeline emit a
simulated alert.

## Reliability Patterns

- Pydantic event envelopes with `event_id`, `event_type`, `occurred_at`, and `correlation_id`.
- Consumer retry and dead-letter publishing to `<topic>.dlq`.
- Consumer idempotency through the `processed_events` table.
- Gateway upstream timeout and retry behavior.
- Correlation ID propagation through HTTP and Kafka.

## Notes

- The KYC service uses `pytesseract` when the Tesseract binary is available and falls back to a deterministic text stub for demo reliability.
- Document uploads are limited by `MAX_DOCUMENT_UPLOAD_BYTES` and stored with collision-resistant names.
- The fraud service loads `models/fraud_isolation_forest.joblib`; if the model does not exist yet, it uses the deterministic fallback scorer.
- SHAP is available for local AI experimentation through `requirements/dev.txt`; runtime containers return deterministic top-feature explanations until a trained model/explainer artifact is added.

## More Docs

- [Architecture Diagram](docs/architecture.md)
- [Architecture Runbook](docs/architecture-runbook.md)
- [Event Contracts](docs/event-contracts.md)
- [API Examples](docs/api-examples.http)
- [Project Status](docs/project-status.md)
- [Postman Collection](docs/postman_collection.json)
