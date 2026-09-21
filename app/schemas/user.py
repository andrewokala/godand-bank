from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=200,
    )

    email: EmailStr

    phone: str = Field(
        min_length=10,
        max_length=20,
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    phone: str
    kyc_status: str
    terms_accepted_at: datetime
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class UserLogin(BaseModel):
    email: EmailStr

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
