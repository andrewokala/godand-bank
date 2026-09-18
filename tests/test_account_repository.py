from datetime import UTC, datetime
from decimal import Decimal

from app.db.session import SessionLocal
from app.models import User
from app.repositories.account import (
    create_account,
    get_account_by_id,
    get_account_by_number,
    get_accounts_by_user_id,
)


def test_account_repository():
    db = SessionLocal()

    email = "account-repository@test.godandbank.local"
    account_number = "9876543210"

    try:
        user = User(
            full_name="Account Test",
            email=email,
            phone="+2348012399001",
            password_hash="test_hash",
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        account = create_account(
            db=db,
            user_id=user.id,
            account_number=account_number,
        )

        assert account.id is not None
        assert account.user_id == user.id
        assert account.account_number == account_number
        assert account.balance == Decimal("0.00")
        assert account.currency == "NGN"
        assert account.status == "active"

        saved_by_id = get_account_by_id(
            db=db,
            account_id=account.id,
        )

        assert saved_by_id is not None
        assert saved_by_id.account_number == account_number

        saved_by_number = get_account_by_number(
            db=db,
            account_number=account_number,
        )

        assert saved_by_number is not None
        assert saved_by_number.id == account.id

        user_accounts = get_accounts_by_user_id(
            db=db,
            user_id=user.id,
        )

        assert len(user_accounts) == 1
        assert user_accounts[0].id == account.id

    finally:
        if "account" in locals() and account.id is not None:
            db.delete(account)

        if "user" in locals() and user.id is not None:
            db.delete(user)

        db.commit()
        db.close()
