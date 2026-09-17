from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Transaction
from app.repositories.account import get_account_by_id


def withdraw(
    db: Session,
    account_id: int,
    amount: Decimal,
    description: str | None = None,
) -> Transaction:
    if amount <= 0:
        raise ValueError("Withdrawal amount must be greater than zero.")

    account = get_account_by_id(
        db=db,
        account_id=account_id,
    )

    if account is None:
        raise ValueError("Account not found.")

    if account.status != "active":
        raise ValueError("Account is not active.")

    if account.balance < amount:
        raise ValueError("Insufficient balance.")

    account.balance -= amount

    transaction = Transaction(
        account_id=account.id,
        transaction_type="withdrawal",
        amount=amount,
        reference=f"WDR-{uuid4().hex[:12].upper()}",
        description=description,
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return transaction
