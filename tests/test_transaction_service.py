from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.models import Transaction, User
from app.repositories.account import create_account
from app.repositories.transaction import create_transaction
from app.services.transaction import get_account_transactions


def test_get_account_transactions_returns_transactions():
    db = SessionLocal()

    user = None
    account = None
    transactions = []

    try:
        user = User(
            first_name="Transaction",
            last_name="Service",
            email="transaction-service@test.godandbank.local",
            password_hash="test_hash",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        account = create_account(
            db=db,
            user_id=user.id,
            account_number="1234567890",
        )

        first_transaction = create_transaction(
            db=db,
            account_id=account.id,
            transaction_type="deposit",
            amount=Decimal("10000.00"),
            reference="TXN-SERVICE-001",
            description="Initial deposit",
        )

        second_transaction = create_transaction(
            db=db,
            account_id=account.id,
            transaction_type="withdrawal",
            amount=Decimal("2500.00"),
            reference="TXN-SERVICE-002",
            description="Cash withdrawal",
        )

        transactions = get_account_transactions(
            db=db,
            account_id=account.id,
        )

        assert len(transactions) == 2
        assert all(
            transaction.account_id == account.id
            for transaction in transactions
        )

    finally:
        for transaction in transactions:
            if transaction.id is not None:
                db.delete(transaction)

        db.commit()

        if account is not None and account.id is not None:
            db.delete(account)

        if user is not None and user.id is not None:
            db.delete(user)

        db.commit()
        db.close()


def test_get_account_transactions_rejects_invalid_account_id():
    db = SessionLocal()

    try:
        with pytest.raises(
            ValueError,
            match="Account ID must be greater than zero",
        ):
            get_account_transactions(
                db=db,
                account_id=0,
            )

    finally:
        db.close()