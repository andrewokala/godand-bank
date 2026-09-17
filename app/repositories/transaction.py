from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction


def create_transaction(
    db: Session,
    account_id: int,
    transaction_type: str,
    amount: Decimal,
    reference: str,
    description: str | None = None,
) -> Transaction:
    transaction = Transaction(
        account_id=account_id,
        transaction_type=transaction_type,
        amount=amount,
        reference=reference,
        description=description,
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return transaction


def get_transaction_by_id(
    db: Session,
    transaction_id: int,
) -> Transaction | None:
    statement = select(Transaction).where(
        Transaction.id == transaction_id
    )

    return db.scalar(statement)


def get_transaction_by_reference(
    db: Session,
    reference: str,
) -> Transaction | None:
    statement = select(Transaction).where(
        Transaction.reference == reference
    )

    return db.scalar(statement)


def get_transactions_by_account_id(
    db: Session,
    account_id: int,
) -> list[Transaction]:
    statement = (
        select(Transaction)
        .where(Transaction.account_id == account_id)
        .order_by(Transaction.created_at.desc())
    )

    return list(db.scalars(statement).all())
