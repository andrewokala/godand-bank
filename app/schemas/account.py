from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AccountResponse(BaseModel):
    id: UUID
    account_number: str
    balance: Decimal
    currency: str
    status: str
    version: int
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }


class AccountCreate(BaseModel):
    account_number: str = Field(
        min_length=10,
        max_length=10,
    )

    currency: str = Field(
        default="NGN",
        min_length=3,
        max_length=3,
    )
