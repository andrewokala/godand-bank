from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TransactionResponse(BaseModel):
    id: int
    account_id: int
    transaction_type: str
    amount: Decimal
    reference: str
    description: str | None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class DepositCreate(BaseModel):
    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
    )

    description: str | None = Field(
        default=None,
        max_length=255,
    )


class WithdrawalCreate(BaseModel):
    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
    )

    description: str | None = Field(
        default=None,
        max_length=255,
    )