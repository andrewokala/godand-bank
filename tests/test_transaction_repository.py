from decimal import Decimal

from app.db.session import SessionLocal
from app.models import User
from app.repositories.account import create_account
from app.repositories.transaction import (
    create_transaction,
    get_transaction_by_id,
    get_transaction_by_reference,
    get_transactions_by_account_id,
)


def test_transaction_repository():
    db = SessionLocal()

    email = "transaction-repository@test.godandbank.local"
    account_number = "8765432109"
    reference = "TXN-REPO-001"

    try:
        user = User(
            first_name="Transaction",
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

        transaction = create_transaction(
            db=db,
            account_id=account.id,
            transaction_type="deposit",
            amount=Decimal("5000.00"),
            reference=reference,
            description="Test deposit",
        )

        assert transaction.id is not None
        assert transaction.account_id == account.id
        assert transaction.transaction_type == "deposit"
        assert transaction.amount == Decimal("5000.00")
        assert transaction.reference == reference
        assert transaction.description == "Test deposit"

        saved_by_id = get_transaction_by_id(
            db=db,
            transaction_id=transaction.id,
        )

        assert saved_by_id is not None
        assert saved_by_id.reference == reference

        saved_by_reference = get_transaction_by_reference(
            db=db,
            reference=reference,
        )

        assert saved_by_reference is not None
        assert saved_by_reference.id == transaction.id

        account_transactions = get_transactions_by_account_id(
            db=db,
            account_id=account.id,
        )

        assert len(account_transactions) == 1
        assert account_transactions[0].id == transaction.id

    finally:
        if "transaction" in locals() and transaction.id is not None:
            db.delete(transaction)

        if "account" in locals() and account.id is not None:
            db.delete(account)

        if "user" in locals() and user.id is not None:
            db.delete(user)

        db.commit()
        db.close()
