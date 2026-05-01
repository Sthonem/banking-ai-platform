from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from banking_common.database import get_db
from banking_common.kafka import KafkaPublisher
from banking_common.metrics import transactions_created_total
from banking_common.models import FraudScore, Transaction, User
from banking_common.observability import configure_observability
from banking_common.schemas import FraudScoreOut, TransactionCreate, TransactionOut


publisher = KafkaPublisher()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await publisher.start()
    yield
    await publisher.stop()


app = FastAPI(title="transaction-service", lifespan=lifespan)
configure_observability(app, "transaction-service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "transaction-service"}


@app.post("/transactions", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(payload: TransactionCreate, request: Request, db: Session = Depends(get_db)) -> Transaction:
    if db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    txn = Transaction(**payload.model_dump())
    db.add(txn)
    db.commit()
    db.refresh(txn)

    transactions_created_total.inc()
    await publisher.publish_event(
        "txn.created",
        "txn.created",
        {
            "transaction_id": txn.id,
            "user_id": txn.user_id,
            "amount": float(txn.amount),
            "currency": txn.currency,
            "merchant": txn.merchant,
            "location": txn.location,
            "device_id": txn.device_id,
            "merchant_category": txn.merchant_category,
            "created_at": txn.created_at,
        },
        correlation_id=request.state.correlation_id,
    )
    return txn


@app.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    user_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[Transaction]:
    query = db.query(Transaction)
    if user_id is not None:
        query = query.filter(Transaction.user_id == user_id)
    return query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit).all()


@app.get("/transactions/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: UUID, db: Session = Depends(get_db)) -> Transaction:
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@app.get("/transactions/{transaction_id}/fraud-scores", response_model=list[FraudScoreOut])
def list_fraud_scores(transaction_id: UUID, db: Session = Depends(get_db)) -> list[FraudScore]:
    if db.get(Transaction, transaction_id) is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return (
        db.query(FraudScore)
        .filter(FraudScore.transaction_id == transaction_id)
        .order_by(FraudScore.created_at.desc())
        .all()
    )
