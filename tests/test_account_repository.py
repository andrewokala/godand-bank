from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

from app.db.session import SessionLocal
from app.models import User
from app.repositories.account import (
    create_account,
    generate_account_number,
    get_account_by_id,
    get_account_by_number,
    get_account_by_number_for_update,
    get_accounts_by_user_id,
)


def test_generate_account_number_skips_existing_number():
    db = SessionLocal()

    email = "account-number-collision@test.godandbank.local"
    existing_account_number = "1234567890"
    next_account_number = "9876543210"

    try:
        user = User(
            full_name="Account Number Test",
            email=email,
            phone="+2348012399002",
            password_hash="test_hash",
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        account = create_account(
            db=db,
            user_id=user.id,
            account_number=existing_account_number,
        )

        with patch(
            "app.repositories.account.secrets.randbelow",
            side_effect=[
                int(existing_account_number),
                int(next_account_number),
            ],
        ):
            generated_number = generate_account_number(db=db)

        assert generated_number == next_account_number

    finally:
        if "account" in locals() and account.id is not None:
            db.delete(account)

        if "user" in locals() and user.id is not None:
            db.delete(user)

        db.commit()
        db.close()


def test_get_account_by_number_for_update_returns_account():
    db = SessionLocal()

    email = "account-lock@test.godandbank.local"
    account_number = "1122334455"

    try:
        user = User(
            full_name="Account Lock Test",
            email=email,
            phone="+2348012399003",
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

        locked_account = get_account_by_number_for_update(
            db=db,
            account_number=account_number,
        )

        assert locked_account is not None
        assert locked_account.id == account.id
        assert locked_account.account_number == account_number

    finally:
        if "account" in locals() and account.id is not None:
            db.delete(account)

        if "user" in locals() and user.id is not None:
            db.delete(user)

        db.commit()
        db.close()


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
