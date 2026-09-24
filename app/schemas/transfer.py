from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class TransferCreate(BaseModel):
    sender_account_number: str = Field(
        min_length=10,
        max_length=10,
    )
    receiver_account_number: str = Field(
        min_length=10,
        max_length=10,
    )
    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
    )
    note: str | None = Field(
        default=None,
        max_length=500,
    )


class TransferResponse(BaseModel):
    id: UUID
    sender_account_id: UUID
    receiver_account_id: UUID
    amount: Decimal
    currency: str
    note: str | None
    reference: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

class TransferHistoryResponse(BaseModel):
    items: list[TransferResponse]
    total: int
    limit: int
    offset: int