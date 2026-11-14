import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from banking_common.config import get_settings
from banking_common.database import get_db
from banking_common.kafka import KafkaPublisher
from banking_common.metrics import kyc_requests_total
from banking_common.models import KycResult, KycStatus, User
from banking_common.observability import configure_observability
from banking_common.schemas import KycResultOut, LoginRequest, TokenOut, UserCreate, UserOut
from banking_common.security import create_access_token, hash_password, require_auth, verify_password

publisher = KafkaPublisher()
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/banking-ai-documents"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    await publisher.start()
    yield
    await publisher.stop()


app = FastAPI(title="onboarding-service", lifespan=lifespan)
configure_observability(app, "onboarding-service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "onboarding-service"}


@app.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> User:
    user = User(name=payload.name, email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered") from exc
    db.refresh(user)
    await publisher.publish_event(
        "user.registered",
        "user.registered",
        {"user_id": user.id, "name": user.name, "email": user.email, "status": user.status.value},
        correlation_id=request.state.correlation_id,
    )
    return user


@app.get("/users", response_model=list[UserOut])
def list_users(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).offset(offset).limit(limit).all()


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: UUID, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenOut:
    user = db.query(User).filter(User.email == payload.email).one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenOut(access_token=create_access_token(str(user.id), {"email": user.email, "role": "customer"}))


@app.post("/users/{user_id}/documents", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    user_id: UUID,
    request: Request,
    document: UploadFile = File(...),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_auth),
) -> dict[str, str]:
    if claims["sub"] != str(user_id):
        raise HTTPException(status_code=403, detail="Cannot upload documents for another user")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if document.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=415, detail="Only JPEG and PNG documents are supported")

    suffix = ".jpg" if document.content_type == "image/jpeg" else ".png"
    raw_document = await document.read()
    if not raw_document:
        raise HTTPException(status_code=400, detail="Uploaded document is empty")
    if len(raw_document) > get_settings().max_document_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded document is too large")

    path = UPLOAD_DIR / f"{user_id}-{uuid4()}{suffix}"
    path.write_bytes(raw_document)
    kyc = KycResult(user_id=user.id, status=KycStatus.pending, document_path=str(path), extracted_fields={})
    db.add(kyc)
    db.commit()
    db.refresh(kyc)

    kyc_requests_total.inc()
    await publisher.publish_event(
        "document.uploaded",
        "document.uploaded",
        {"user_id": user.id, "kyc_result_id": kyc.id, "document_path": str(path)},
        correlation_id=request.state.correlation_id,
    )
    return {"status": "queued", "kyc_result_id": str(kyc.id)}


@app.get("/users/{user_id}/kyc-results", response_model=list[KycResultOut])
def list_user_kyc_results(user_id: UUID, db: Session = Depends(get_db)) -> list[KycResult]:
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db.query(KycResult).filter(KycResult.user_id == user_id).order_by(KycResult.created_at.desc()).all()


@app.get("/kyc-results/{kyc_result_id}", response_model=KycResultOut)
def get_kyc_result(kyc_result_id: UUID, db: Session = Depends(get_db)) -> KycResult:
    result = db.get(KycResult, kyc_result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="KYC result not found")
    return result
