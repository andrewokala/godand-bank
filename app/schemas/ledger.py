from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import LedgerDirection


class LedgerEntryResponse(BaseModel):
    id: UUID
    transfer_id: UUID
    account_id: UUID
    direction: LedgerDirection
    amount: Decimal
    balance_after: Decimal
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
