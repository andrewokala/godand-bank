from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.models import Account, Transaction, Transfer, User
from app.services.transfer import transfer


def test_transfer_moves_money_between_accounts():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    try:
        sender_user = User(
            first_name="Sender",
            last_name="User",
            email="transfer-sender@test.godandbank.local",
            password_hash="test_hash",
        )

        receiver_user = User(
            first_name="Receiver",
            last_name="User",
            email="transfer-receiver@test.godandbank.local",
            password_hash="test_hash",
        )

        db.add_all([sender_user, receiver_user])
        db.commit()
        db.refresh(sender_user)
        db.refresh(receiver_user)

        sender_account = Account(
            user_id=sender_user.id,
            account_number="1111111111",
            balance=Decimal("10000.00"),
            currency="NGN",
            status="active",
        )

        receiver_account = Account(
            user_id=receiver_user.id,
            account_number="2222222222",
            balance=Decimal("5000.00"),
            currency="NGN",
            status="active",
        )

        db.add_all([sender_account, receiver_account])
        db.commit()
        db.refresh(sender_account)
        db.refresh(receiver_account)

        result = transfer(
            db=db,
            sender_account_number="1111111111",
            receiver_account_number="2222222222",
            amount=Decimal("3000.00"),
        )

        db.refresh(sender_account)
        db.refresh(receiver_account)

        assert sender_account.balance == Decimal("7000.00")
        assert receiver_account.balance == Decimal("8000.00")

        assert result.sender_account_id == sender_account.id
        assert result.receiver_account_id == receiver_account.id
        assert result.amount == Decimal("3000.00")
        assert result.status == "completed"
        assert result.reference.startswith("TRF-")

        sender_transaction = (
            db.query(Transaction)
            .filter(
                Transaction.account_id == sender_account.id,
                Transaction.transaction_type == "transfer_out",
            )
            .first()
        )

        receiver_transaction = (
            db.query(Transaction)
            .filter(
                Transaction.account_id == receiver_account.id,
                Transaction.transaction_type == "transfer_in",
            )
            .first()
        )

        assert sender_transaction is not None
        assert receiver_transaction is not None

        assert sender_transaction.amount == Decimal("3000.00")
        assert receiver_transaction.amount == Decimal("3000.00")

        assert sender_transaction.reference == f"{result.reference}-OUT"
        assert receiver_transaction.reference == f"{result.reference}-IN"

    finally:
        if sender_account is not None:
            db.query(Transaction).filter(
                Transaction.account_id == sender_account.id
            ).delete(synchronize_session=False)

        if receiver_account is not None:
            db.query(Transaction).filter(
                Transaction.account_id == receiver_account.id
            ).delete(synchronize_session=False)

        if sender_account is not None:
            db.query(Transfer).filter(
                (Transfer.sender_account_id == sender_account.id)
                | (Transfer.receiver_account_id == sender_account.id)
            ).delete(synchronize_session=False)

        if receiver_account is not None:
            db.query(Transfer).filter(
                (Transfer.sender_account_id == receiver_account.id)
                | (Transfer.receiver_account_id == receiver_account.id)
            ).delete(synchronize_session=False)

        if sender_account is not None:
            db.delete(sender_account)

        if receiver_account is not None:
            db.delete(receiver_account)

        if sender_user is not None:
            db.delete(sender_user)

        if receiver_user is not None:
            db.delete(receiver_user)

        db.commit()
        db.close()


def test_transfer_rejects_insufficient_balance():
    db = SessionLocal()

    user = None
    receiver = None
    account = None
    receiver_account = None

    try:
        user = User(
            first_name="Sender",
            last_name="User",
            email="insufficient-transfer@test.godandbank.local",
            password_hash="test_hash",
        )

        receiver = User(
            first_name="Receiver",
            last_name="User",
            email="insufficient-transfer-receiver@test.godandbank.local",
            password_hash="test_hash",
        )

        db.add_all([user, receiver])
        db.commit()
        db.refresh(user)
        db.refresh(receiver)

        account = Account(
            user_id=user.id,
            account_number="3333333333",
            balance=Decimal("1000.00"),
            currency="NGN",
            status="active",
        )

        receiver_account = Account(
            user_id=receiver.id,
            account_number="4444444444",
            balance=Decimal("500.00"),
            currency="NGN",
            status="active",
        )

        db.add_all([account, receiver_account])
        db.commit()

        with pytest.raises(ValueError, match="Insufficient balance"):
            transfer(
                db=db,
                sender_account_number="3333333333",
                receiver_account_number="4444444444",
                amount=Decimal("2000.00"),
            )

    finally:
        if account is not None:
            db.query(Transaction).filter(
                Transaction.account_id == account.id
            ).delete(synchronize_session=False)

        if receiver_account is not None:
            db.query(Transaction).filter(
                Transaction.account_id == receiver_account.id
            ).delete(synchronize_session=False)

        if account is not None:
            db.delete(account)

        if receiver_account is not None:
            db.delete(receiver_account)

        if user is not None:
            db.delete(user)

        if receiver is not None:
            db.delete(receiver)

        db.commit()
        db.close()


def test_transfer_rejects_zero_amount():
    db = SessionLocal()

    try:
        with pytest.raises(
            ValueError,
            match="Transfer amount must be greater than zero",
        ):
            transfer(
                db=db,
                sender_account_number="1111111111",
                receiver_account_number="2222222222",
                amount=Decimal("0.00"),
            )

    finally:
        db.close()


def test_transfer_rejects_self_transfer():
    db = SessionLocal()

    try:
        with pytest.raises(
            ValueError,
            match="Sender and receiver accounts must be different",
        ):
            transfer(
                db=db,
                sender_account_number="1111111111",
                receiver_account_number="1111111111",
                amount=Decimal("100.00"),
            )

    finally:
        db.close()


def test_transfer_rejects_missing_sender():
    db = SessionLocal()

    try:
        with pytest.raises(
            ValueError,
            match="Sender account not found",
        ):
            transfer(
                db=db,
                sender_account_number="9999999999",
                receiver_account_number="2222222222",
                amount=Decimal("100.00"),
            )

    finally:
        db.close()


def test_transfer_rejects_missing_receiver():
    db = SessionLocal()

    user = None
    account = None

    try:
        user = User(
            first_name="Sender",
            last_name="User",
            email="missing-receiver@test.godandbank.local",
            password_hash="test_hash",
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        account = Account(
            user_id=user.id,
            account_number="5555555555",
            balance=Decimal("5000.00"),
            currency="NGN",
            status="active",
        )

        db.add(account)
        db.commit()
        db.refresh(account)

        with pytest.raises(
            ValueError,
            match="Receiver account not found",
        ):
            transfer(
                db=db,
                sender_account_number="5555555555",
                receiver_account_number="9999999999",
                amount=Decimal("100.00"),
            )

    finally:
        if account is not None:
            db.query(Transaction).filter(
                Transaction.account_id == account.id
            ).delete(synchronize_session=False)

            db.delete(account)

        if user is not None:
            db.delete(user)

        db.commit()
        db.close()

