from prometheus_client import Counter, Histogram


kyc_requests_total = Counter("kyc_requests_total", "KYC documents queued")
kyc_approved_total = Counter("kyc_approved_total", "KYC approvals")
kyc_rejected_total = Counter("kyc_rejected_total", "KYC rejections")
transactions_created_total = Counter("transactions_created_total", "Transactions created")
fraud_detected_total = Counter("fraud_detected_total", "Fraud alerts emitted")
fraud_score_histogram = Histogram("fraud_score_histogram", "Fraud model score distribution")
event_failures_total = Counter("event_failures_total", "Kafka consumer failures", ["topic", "event_type"])
