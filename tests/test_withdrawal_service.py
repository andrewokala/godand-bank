from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.models import User
from app.repositories.account import create_account
from app.services.deposit import deposit
from app.services.withdrawal import withdraw


def test_withdrawal_reduces_balance_and_creates_transaction():
    db = SessionLocal()

    email = "withdrawal-service@test.godandbank.local"
    account_number = "4321098765"

    try:
        user = User(
            first_name="Withdrawal",
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

        deposit_transaction = deposit(
            db=db,
            account_id=account.id,
            amount=Decimal("10000.00"),
        )

        transaction = withdraw(
            db=db,
            account_id=account.id,
            amount=Decimal("3500.00"),
            description="Test withdrawal",
        )

        db.refresh(account)

        assert account.balance == Decimal("6500.00")

        assert transaction.account_id == account.id
        assert transaction.transaction_type == "withdrawal"
        assert transaction.amount == Decimal("3500.00")
        assert transaction.description == "Test withdrawal"
        assert transaction.reference.startswith("WDR-")

    finally:
        if "transaction" in locals() and transaction.id is not None:
            db.delete(transaction)

        if (
            "deposit_transaction" in locals()
            and deposit_transaction.id is not None
        ):
            db.delete(deposit_transaction)

        if "account" in locals() and account.id is not None:
            db.delete(account)

        if "user" in locals() and user.id is not None:
            db.delete(user)

        db.commit()
        db.close()

def test_withdrawal_rejects_insufficient_balance():
    db = SessionLocal()

    email = "insufficient-withdrawal@test.godandbank.local"
    account_number = "3210987654"

    try:
        user = User(
            first_name="Insufficient",
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

        deposit_transaction = deposit(
            db=db,
            account_id=account.id,
            amount=Decimal("1000.00"),
        )

        with pytest.raises(ValueError, match="Insufficient balance"):
            withdraw(
                db=db,
                account_id=account.id,
                amount=Decimal("1500.00"),
            )

        db.refresh(account)

        assert account.balance == Decimal("1000.00")

    finally:
        if (
            "deposit_transaction" in locals()
            and deposit_transaction.id is not None
        ):
            db.delete(deposit_transaction)

        if "account" in locals() and account.id is not None:
            db.delete(account)

        if "user" in locals() and user.id is not None:
            db.delete(user)

        db.commit()
        db.close()


def test_withdrawal_rejects_zero_amount():
    db = SessionLocal()

    try:
        with pytest.raises(
            ValueError,
            match="greater than zero",
        ):
            withdraw(
                db=db,
                account_id=999999999,
                amount=Decimal("0.00"),
            )
    finally:
        db.close()


def test_withdrawal_rejects_missing_account():
    db = SessionLocal()

    try:
        with pytest.raises(ValueError, match="Account not found"):
            withdraw(
                db=db,
                account_id=999999999,
                amount=Decimal("1000.00"),
            )
    finally:
        db.close()
