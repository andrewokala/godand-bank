import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserLogin, UserResponse

from decimal import Decimal

from datetime import datetime

from app.schemas.account import AccountCreate, AccountResponse

from app.schemas.transaction import (
    DepositCreate,
    TransactionResponse,
    WithdrawalCreate,
)


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


def test_user_response_does_not_expose_password_hash():
    user = UserResponse(
        id=1,
        first_name="Godwin",
        last_name="Ejeme",
        email="godwin@example.com",
        created_at="2026-09-17T10:00:00Z",
        updated_at="2026-09-17T10:00:00Z",
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


def test_account_response_accepts_decimal_balance():
    account = AccountResponse(
        id=1,
        account_number="1234567890",
        balance=Decimal("5000.00"),
        currency="NGN",
        status="active",
        created_at="2026-09-17T10:00:00Z",
        updated_at="2026-09-17T10:00:00Z",
    )

    assert account.balance == Decimal("5000.00")
    assert account.currency == "NGN"

def test_deposit_create_accepts_positive_amount():
    deposit = DepositCreate(
        amount=Decimal("5000.00"),
        description="Initial deposit",
    )

    assert deposit.amount == Decimal("5000.00")
    assert deposit.description == "Initial deposit"


def test_withdrawal_create_accepts_positive_amount():
    withdrawal = WithdrawalCreate(
        amount=Decimal("1000.00"),
        description="Cash withdrawal",
    )

    assert withdrawal.amount == Decimal("1000.00")
    assert withdrawal.description == "Cash withdrawal"


def test_deposit_rejects_zero_amount():
    with pytest.raises(ValidationError):
        DepositCreate(
            amount=Decimal("0.00"),
        )


def test_withdrawal_rejects_negative_amount():
    with pytest.raises(ValidationError):
        WithdrawalCreate(
            amount=Decimal("-100.00"),
        )


def test_transaction_response_accepts_valid_data():
    transaction = TransactionResponse(
        id=1,
        account_id=1,
        transaction_type="deposit",
        amount=Decimal("5000.00"),
        reference="TXN-123456",
        description="Initial deposit",
        created_at="2026-09-17T10:00:00Z",
    )

    assert transaction.amount == Decimal("5000.00")
    assert transaction.transaction_type == "deposit"
    assert transaction.reference == "TXN-123456"

from app.schemas.transfer import TransferCreate, TransferResponse


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


def test_transfer_response_accepts_valid_data():
    transfer = TransferResponse(
        id=1,
        sender_account_id=10,
        receiver_account_id=20,
        amount=Decimal("2500.00"),
        reference="TRF-001",
        status="completed",
        created_at=datetime.now(),
    )

    assert transfer.amount == Decimal("2500.00")
    assert transfer.status == "completed"