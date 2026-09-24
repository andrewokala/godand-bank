import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LedgerEntry


def get_ledger_entries_by_account_id(
    db: Session,
    account_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[LedgerEntry], int]:
    base_statement = select(LedgerEntry).where(
        LedgerEntry.account_id == account_id
    )

    total = db.scalar(
        select(func.count()).select_from(
            base_statement.subquery()
        )
    )

    statement = (
        base_statement
        .order_by(
            LedgerEntry.created_at.desc(),
            LedgerEntry.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    entries = list(db.scalars(statement).all())

    return entries, total or 0
