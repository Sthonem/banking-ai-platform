# System Architecture

## Component Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              External Client                                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ HTTP
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              api-gateway :8080                              │
│                                                                             │
│  • JWT verification (public routes bypassed)                                │
│  • Redis-backed rate limiting (per IP per path, 120 req/min)                │
│  • Upstream retry (3 attempts, 502 on failure)                              │
│  • x-correlation-id injection                                               │
└──────────────────────┬──────────────────────┬───────────────────────────────┘
                       │ /onboarding/*         │ /transactions/*
                       ▼                       ▼
        ┌──────────────────────┐   ┌──────────────────────┐
        │  onboarding-service  │   │ transaction-service  │
        │       :8001          │   │       :8002          │
        │                      │   │                      │
        │  POST /users         │   │  POST /transactions  │
        │  POST /auth/login    │   │  GET  /transactions  │
        │  POST /{id}/docs     │   │  GET  /{id}/fraud-   │
        │  GET  /kyc-results   │   │       scores         │
        └──────────┬───────────┘   └──────────┬───────────┘
                   │                          │
                   │ writes                   │ writes
                   ▼                          ▼
        ┌──────────────────────────────────────────────────┐
        │                   PostgreSQL :5432               │
        │                                                  │
        │  users  kyc_results  transactions  fraud_scores  │
        │  processed_events                                │
        └──────────────────────────────────────────────────┘

                   │ publishes                │ publishes
                   ▼                          ▼
        ┌──────────────────────────────────────────────────┐
        │                    Kafka :9092                   │
        │                                                  │
        │  user.registered     document.uploaded           │
        │  user.kyc.completed  txn.created                 │
        │  fraud.detected      *.dlq (dead-letter)         │
        └────────┬───────────────────────┬─────────────────┘
                 │ document.uploaded     │ txn.created
                 ▼                       ▼
    ┌────────────────────┐   ┌─────────────────────────┐
    │   kyc-ai-service   │   │    fraud-ai-service      │
    │                    │   │                         │
    │  pytesseract OCR   │   │  IsolationForest model  │
    │  spaCy NER         │   │  (fallback scorer)      │
    │  regex extraction  │   │                         │
    │                    │   │  Features:              │
    │  → updates         │   │  • amount               │
    │    kyc_results     │   │  • time_since_last_txn  │
    │  → sets user       │   │  • location_change_km   │
    │    status          │   │  • merchant_category    │
    │                    │   │  • device_seen_before   │
    └─────────┬──────────┘   │  • txn_count_5min ←──┐ │
              │               └──────────┬────────────┼─┘
              │ user.kyc.completed       │            │
              │                 fraud.detected        │ Redis INCR
              ▼                          ▼            │ (5-min window)
        ┌──────────────────────────────────────────────────┐
        │                  alert-service                   │
        │                                                  │
        │  Consumes KYC + fraud events                     │
        │  Logs simulated notifications                    │
        └──────────────────────────────────────────────────┘

## Observability Stack

        ┌─────────────┐    scrapes /metrics    ┌──────────────────┐
        │  Prometheus │ ◄─────────────────────  │  All services    │
        │    :9090    │                         │  (FastAPI instr.)│
        └──────┬──────┘                         └──────────────────┘
               │ datasource
               ▼
        ┌─────────────┐        ┌──────────────────┐
        │   Grafana   │        │     Zipkin        │
        │    :3000    │        │     :9411         │
        │             │        │                  │
        │  Dashboard: │        │  Distributed     │
        │  - txn vol  │        │  tracing via     │
        │  - fraud %  │        │  OpenTelemetry   │
        │  - avg score│        │  (all services)  │
        └─────────────┘        └──────────────────┘

## Request Lifecycle — End-to-End Demo

  1. POST /onboarding/users
       → user row created (status: pending_kyc)
       → user.registered event → Kafka

  2. POST /onboarding/users/{id}/documents  [requires Bearer token]
       → JWT sub == user_id enforced
       → file saved to /tmp/banking-ai-documents
       → kyc_results row created (status: pending)
       → document.uploaded event → Kafka

  3. kyc-ai-service consumes document.uploaded
       → OCR + NER extraction
       → kyc_results updated (status: approved | rejected)
       → user status updated (active | rejected)
       → user.kyc.completed event → Kafka

  4. POST /transactions  [requires Bearer token]
       → transaction row created
       → txn.created event → Kafka

  5. fraud-ai-service consumes txn.created
       → Redis INCR velocity key (5-min TTL)
       → derive 6 features from DB + Redis
       → score via IsolationForest (or fallback)
       → fraud_scores row written with SHAP-style explanation
       → if score ≥ threshold: fraud.detected event → Kafka

  6. alert-service consumes fraud.detected + user.kyc.completed
       → logs SIMULATED ALERT / SIMULATED NOTIFICATION

## Reliability Patterns

  • Event envelope:    event_id, event_type, occurred_at, correlation_id
  • Idempotency:       processed_events table (unique event_id + consumer_name)
  • Retry + DLQ:       3 attempts per message → <topic>.dlq on failure
  • Rate limiting:     Redis INCR + EXPIRE at gateway
  • Correlation ID:    propagated HTTP header → Kafka payload → logs
  • Model fallback:    deterministic scorer when .joblib not present
  • OCR fallback:      stub text when Tesseract unavailable
```
