from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.models import User
from app.repositories.account import create_account
from app.services.deposit import deposit


def test_deposit_increases_balance_and_creates_transaction():
    db = SessionLocal()

    email = "deposit-service@test.godandbank.local"
    account_number = "5432109876"

    try:
        user = User(
            first_name="Deposit",
            last_name="Test",
            email=email,
            password_hash="test_hash",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        account = create_account(
            db=db,
            user_id=user.id,
            account_number=account_number,
        )

        transaction = deposit(
            db=db,
            account_id=account.id,
            amount=Decimal("10000.00"),
            description="Initial deposit",
        )

        db.refresh(account)

        assert account.balance == Decimal("10000.00")

        assert transaction.account_id == account.id
        assert transaction.transaction_type == "deposit"
        assert transaction.amount == Decimal("10000.00")
        assert transaction.description == "Initial deposit"
        assert transaction.reference.startswith("DEP-")

    finally:
        if "transaction" in locals() and transaction.id is not None:
            db.delete(transaction)

        if "account" in locals() and account.id is not None:
            db.delete(account)

        if "user" in locals() and user.id is not None:
            db.delete(user)

        db.commit()
        db.close()


def test_deposit_rejects_zero_amount():
    db = SessionLocal()

    try:
        with pytest.raises(ValueError, match="greater than zero"):
            deposit(
                db=db,
                account_id=999999999,
                amount=Decimal("0.00"),
            )
    finally:
        db.close()


def test_deposit_rejects_missing_account():
    db = SessionLocal()

    try:
        with pytest.raises(ValueError, match="Account not found"):
            deposit(
                db=db,
                account_id=999999999,
                amount=Decimal("1000.00"),
            )
    finally:
        db.close()
