import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Transfer, TransferStatus


def create_transfer(
    db: Session,
    sender_account_id: uuid.UUID,
    receiver_account_id: uuid.UUID,
    amount: Decimal,
    reference: str,
    currency: str = "NGN",
    idempotency_key: str | None = None,
    note: str | None = None,
    status: TransferStatus = TransferStatus.SUCCESS,
) -> Transfer:
    transfer = Transfer(
        sender_account_id=sender_account_id,
        receiver_account_id=receiver_account_id,
        amount=amount,
        currency=currency,
        reference=reference,
        idempotency_key=idempotency_key or f"repo-{uuid.uuid4()}",
        note=note,
        status=status,
    )

    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    return transfer


def get_transfer_by_id(
    db: Session,
    transfer_id: uuid.UUID,
) -> Transfer | None:
    statement = select(Transfer).where(
        Transfer.id == transfer_id
    )

    return db.scalar(statement)


def get_transfer_by_reference(
    db: Session,
    reference: str,
) -> Transfer | None:
    statement = select(Transfer).where(
        Transfer.reference == reference
    )

    return db.scalar(statement)


def get_transfers_by_account_id(
    db: Session,
    account_id: uuid.UUID,
) -> list[Transfer]:
    statement = (
        select(Transfer)
        .where(
            (Transfer.sender_account_id == account_id)
            | (Transfer.receiver_account_id == account_id)
        )
        .order_by(Transfer.created_at.desc())
    )

    return list(db.scalars(statement).all())

def get_transfers_by_account_ids(
    db: Session,
    account_ids: list[uuid.UUID],
    limit: int,
    offset: int,
) -> tuple[list[Transfer], int]:
    if not account_ids:
        return [], 0

    transfer_filter = (
        (Transfer.sender_account_id.in_(account_ids))
        | (Transfer.receiver_account_id.in_(account_ids))
    )

    total_statement = (
        select(func.count())
        .select_from(Transfer)
        .where(transfer_filter)
    )

    total = db.scalar(total_statement) or 0

    statement = (
        select(Transfer)
        .where(transfer_filter)
        .order_by(
            Transfer.created_at.desc(),
            Transfer.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    transfers = list(db.scalars(statement).all())

    return transfers, total
