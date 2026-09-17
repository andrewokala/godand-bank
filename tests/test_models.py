from decimal import Decimal

from app.db.session import SessionLocal
from app.models import Account, User


def test_create_user_and_account():
    db = SessionLocal()

    try:
        user = User(
            first_name="Test",
            last_name="User",
            email="test@godandbank.local",
            password_hash="test_hash",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        account = Account(
            user_id=user.id,
            account_number="1234567890",
            balance=Decimal("5000.00"),
            currency="NGN",
            status="active",
        )

        db.add(account)
        db.commit()
        db.refresh(account)

        saved_user = db.get(User, user.id)
        saved_account = db.get(Account, account.id)

        assert saved_user is not None
        assert saved_user.email == "test@godandbank.local"

        assert saved_account is not None
        assert saved_account.balance == Decimal("5000.00")
        assert saved_account.currency == "NGN"

    finally:
        if "account" in locals() and account.id is not None:
            db.delete(account)

        if "user" in locals() and user.id is not None:
            db.delete(user)

        db.commit()
        db.close()