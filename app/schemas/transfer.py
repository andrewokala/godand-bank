from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TransferCreate(BaseModel):
    receiver_account_number: str = Field(
        min_length=10,
        max_length=10,
    )

    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
    )


class TransferResponse(BaseModel):
    id: int
    sender_account_id: int
    receiver_account_id: int
    amount: Decimal
    reference: str
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }