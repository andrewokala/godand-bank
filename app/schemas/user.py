from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


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


class SignupRequest(UserCreate):
    terms_accepted: bool

    @model_validator(mode="after")
    def validate_terms(self):
        if self.terms_accepted is not True:
            raise ValueError(
                "You must accept the terms and conditions."
            )
        return self


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
