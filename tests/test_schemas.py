import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.account import AccountCreate, AccountResponse
from app.schemas.transfer import TransferCreate, TransferResponse
from app.schemas.user import UserCreate, UserLogin, UserResponse


def test_user_create_accepts_valid_data():
    user = UserCreate(
        first_name="Godwin",
        last_name="Ejeme",
        email="godwin@example.com",
        password="securepass123",
    )

    assert user.first_name == "Godwin"
    assert user.last_name == "Ejeme"
    assert user.email == "godwin@example.com"


def test_user_create_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserCreate(
            first_name="Godwin",
            last_name="Ejeme",
            email="not-an-email",
            password="securepass123",
        )


def test_user_create_rejects_short_password():
    with pytest.raises(ValidationError):
        UserCreate(
            first_name="Godwin",
            last_name="Ejeme",
            email="godwin@example.com",
            password="short",
        )


def test_user_login_accepts_valid_data():
    login = UserLogin(
        email="godwin@example.com",
        password="securepass123",
    )

    assert login.email == "godwin@example.com"
    assert login.password == "securepass123"


def test_user_response_does_not_expose_password_hash():
    user = UserResponse(
        id=uuid.uuid4(),
        first_name="Godwin",
        last_name="Ejeme",
        email="godwin@example.com",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    assert "password_hash" not in user.model_dump()


def test_account_create_accepts_valid_data():
    account = AccountCreate(
        account_number="1234567890",
        currency="NGN",
    )

    assert account.account_number == "1234567890"
    assert account.currency == "NGN"


def test_account_create_uses_ngn_by_default():
    account = AccountCreate(
        account_number="1234567890",
    )

    assert account.currency == "NGN"


def test_account_create_rejects_invalid_account_number():
    with pytest.raises(ValidationError):
        AccountCreate(
            account_number="12345",
            currency="NGN",
        )


def test_account_response_accepts_uuid_and_decimal_balance():
    account_id = uuid.uuid4()

    account = AccountResponse(
        id=account_id,
        account_number="1234567890",
        balance=Decimal("5000.00"),
        currency="NGN",
        status="active",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    assert account.id == account_id
    assert account.balance == Decimal("5000.00")
    assert account.currency == "NGN"


def test_transfer_create_accepts_valid_data():
    transfer = TransferCreate(
        receiver_account_number="9876543210",
        amount=Decimal("2500.00"),
    )

    assert transfer.receiver_account_number == "9876543210"
    assert transfer.amount == Decimal("2500.00")


def test_transfer_create_rejects_invalid_account_number():
    with pytest.raises(ValidationError):
        TransferCreate(
            receiver_account_number="12345",
            amount=Decimal("2500.00"),
        )


def test_transfer_create_rejects_invalid_amount():
    with pytest.raises(ValidationError):
        TransferCreate(
            receiver_account_number="9876543210",
            amount=Decimal("0.00"),
        )


def test_transfer_response_accepts_uuid_fields():
    transfer_id = uuid.uuid4()
    sender_id = uuid.uuid4()
    receiver_id = uuid.uuid4()

    transfer = TransferResponse(
        id=transfer_id,
        sender_account_id=sender_id,
        receiver_account_id=receiver_id,
        amount=Decimal("2500.00"),
        currency="NGN",
        note="Test transfer",
        reference="TRF-001",
        status="success",
        created_at=datetime.now(),
    )

    assert transfer.id == transfer_id
    assert transfer.sender_account_id == sender_id
    assert transfer.receiver_account_id == receiver_id
    assert transfer.amount == Decimal("2500.00")
    assert transfer.currency == "NGN"
    assert transfer.note == "Test transfer"
    assert transfer.status == "success"
