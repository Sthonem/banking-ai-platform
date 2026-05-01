from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class KycResultOut(BaseModel):
    id: UUID
    user_id: UUID
    status: str
    ocr_text: str | None
    extracted_fields: dict
    document_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TransactionCreate(BaseModel):
    user_id: UUID
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    merchant: str
    location: str
    device_id: str
    merchant_category: str = "general"


class TransactionOut(BaseModel):
    id: UUID
    user_id: UUID
    amount: float
    currency: str
    merchant: str
    location: str
    device_id: str
    merchant_category: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FraudScoreOut(BaseModel):
    id: UUID
    transaction_id: UUID
    score: float
    is_fraud: bool
    explanation: dict
    created_at: datetime

    model_config = {"from_attributes": True}
