from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transfer


def create_transfer(
    db: Session,
    sender_account_id: int,
    receiver_account_id: int,
    amount: Decimal,
    reference: str,
    status: str = "completed",
) -> Transfer:
    transfer = Transfer(
        sender_account_id=sender_account_id,
        receiver_account_id=receiver_account_id,
        amount=amount,
        reference=reference,
        status=status,
    )

    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    return transfer


def get_transfer_by_id(
    db: Session,
    transfer_id: int,
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
    account_id: int,
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
