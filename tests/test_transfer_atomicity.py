from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.models import (
    Account,
    AccountStatus,
    AuditLog,
    IdempotencyKey,
    KYCStatus,
    LedgerEntry,
    Transfer,
    User,
)
from app.services.transfer import transfer


def create_test_accounts(
    db,
    sender_balance=Decimal("10000.00"),
    receiver_balance=Decimal("5000.00"),
):
    sender_user = User(
        full_name="Atomicity Sender",
        email=f"sender-{uuid4().hex}@test.godandbank.local",
        phone=f"+23480{uuid4().int % 10_000_000:07d}",
        password_hash="test_hash",
        kyc_status=KYCStatus.VERIFIED,
        terms_accepted_at=datetime.now(UTC),
    )

    receiver_user = User(
        full_name="Atomicity Receiver",
        email=f"receiver-{uuid4().hex}@test.godandbank.local",
        phone=f"+23481{uuid4().int % 10_000_000:07d}",
        password_hash="test_hash",
        kyc_status=KYCStatus.VERIFIED,
        terms_accepted_at=datetime.now(UTC),
    )

    db.add_all([sender_user, receiver_user])
    db.flush()

    sender_account = Account(
        user_id=sender_user.id,
        account_number=f"{uuid4().int % 10_000_000_00:010d}",
        balance=sender_balance,
        currency="NGN",
        status=AccountStatus.ACTIVE,
    )

    receiver_account = Account(
        user_id=receiver_user.id,
        account_number=f"{uuid4().int % 10_000_000_00:010d}",
        balance=receiver_balance,
        currency="NGN",
        status=AccountStatus.ACTIVE,
    )

    db.add_all([sender_account, receiver_account])
    db.commit()

    db.refresh(sender_account)
    db.refresh(receiver_account)

    return (
        sender_user,
        receiver_user,
        sender_account,
        receiver_account,
    )


def cleanup_accounts(db, users, *accounts):
    account_ids = [
        account.id
        for account in accounts
        if account is not None
    ]

    user_ids = [
        user.id
        for user in users
        if user is not None
    ]

    if account_ids:
        transfer_ids = [
            transfer.id
            for transfer in db.query(Transfer).filter(
                (Transfer.sender_account_id.in_(account_ids))
                | (Transfer.receiver_account_id.in_(account_ids))
            ).all()
        ]

        if transfer_ids:
            db.query(LedgerEntry).filter(
                LedgerEntry.transfer_id.in_(transfer_ids)
            ).delete(synchronize_session=False)

            db.query(Transfer).filter(
                Transfer.id.in_(transfer_ids)
            ).delete(synchronize_session=False)

        db.query(LedgerEntry).filter(
            LedgerEntry.account_id.in_(account_ids)
        ).delete(synchronize_session=False)

        db.query(Account).filter(
            Account.id.in_(account_ids)
        ).delete(synchronize_session=False)

    if user_ids:
        db.query(AuditLog).filter(
            AuditLog.actor_user_id.in_(user_ids)
        ).delete(synchronize_session=False)

        db.query(IdempotencyKey).filter(
            IdempotencyKey.user_id.in_(user_ids)
        ).delete(synchronize_session=False)

        db.query(User).filter(
            User.id.in_(user_ids)
        ).delete(synchronize_session=False)


def test_transfer_rolls_back_all_changes_when_audit_fails(monkeypatch):
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    idempotency_key = f"atomicity-{uuid4().hex}"

    def failing_audit_event(*args, **kwargs):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr(
        "app.services.transfer.record_audit_event",
        failing_audit_event,
    )

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        original_sender_balance = sender_account.balance
        original_receiver_balance = receiver_account.balance

        with pytest.raises(
            RuntimeError,
            match="Simulated audit failure",
        ):
            transfer(
                db=db,
                user_id=sender_user.id,
                idempotency_key=idempotency_key,
                sender_account_number=sender_account.account_number,
                receiver_account_number=receiver_account.account_number,
                amount=Decimal("3000.00"),
                currency="NGN",
                ip_address="127.0.0.1",
            )

        db.refresh(sender_account)
        db.refresh(receiver_account)

        assert sender_account.balance == original_sender_balance
        assert receiver_account.balance == original_receiver_balance

        assert (
            db.query(Transfer)
            .filter(
                Transfer.sender_account_id == sender_account.id,
                Transfer.receiver_account_id == receiver_account.id,
            )
            .count()
            == 0
        )

        assert (
            db.query(LedgerEntry)
            .filter(
                LedgerEntry.account_id.in_(
                    [sender_account.id, receiver_account.id]
                )
            )
            .count()
            == 0
        )

        assert (
            db.query(IdempotencyKey)
            .filter(
                IdempotencyKey.key == idempotency_key
            )
            .count()
            == 0
        )

        assert (
            db.query(AuditLog)
            .filter(
                AuditLog.actor_user_id == sender_user.id,
                AuditLog.action == "transfer.created",
            )
            .count()
            == 0
        )

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        db.commit()
        db.close()

def test_transfer_rolls_back_when_database_integrity_error_occurs(monkeypatch):
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    idempotency_key = f"integrity-{uuid4().hex}"

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        original_sender_balance = sender_account.balance
        original_receiver_balance = receiver_account.balance

        original_flush = db.flush
        flush_calls = 0

        def failing_flush(*args, **kwargs):
            nonlocal flush_calls

            flush_calls += 1

            if flush_calls == 2:
                raise IntegrityError(
                    "Simulated database failure",
                    {},
                    Exception("duplicate key"),
                )

            return original_flush(*args, **kwargs)

        monkeypatch.setattr(db, "flush", failing_flush)

        with pytest.raises(IntegrityError):
            transfer(
                db=db,
                user_id=sender_user.id,
                idempotency_key=idempotency_key,
                sender_account_number=sender_account.account_number,
                receiver_account_number=receiver_account.account_number,
                amount=Decimal("3000.00"),
                currency="NGN",
            )

        db.refresh(sender_account)
        db.refresh(receiver_account)

        assert sender_account.balance == original_sender_balance
        assert receiver_account.balance == original_receiver_balance

        assert (
            db.query(Transfer)
            .filter(
                Transfer.sender_account_id == sender_account.id,
                Transfer.receiver_account_id == receiver_account.id,
            )
            .count()
            == 0
        )

        assert (
            db.query(LedgerEntry)
            .filter(
                LedgerEntry.account_id.in_(
                    [sender_account.id, receiver_account.id]
                )
            )
            .count()
            == 0
        )

        assert (
            db.query(IdempotencyKey)
            .filter(
                IdempotencyKey.key == idempotency_key
            )
            .count()
            == 0
        )

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        db.commit()
        db.close()
