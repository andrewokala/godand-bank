import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LedgerEntry


def get_ledger_entries_by_account_id(
    db: Session,
    account_id: uuid.UUID,
) -> list[LedgerEntry]:
    statement = (
        select(LedgerEntry)
        .where(LedgerEntry.account_id == account_id)
        .order_by(
            LedgerEntry.created_at.desc(),
            LedgerEntry.id.desc(),
        )
    )

    return list(db.scalars(statement).all())
