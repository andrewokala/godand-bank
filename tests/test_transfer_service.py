from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.session import SessionLocal
from app.models import (
    AuditLog,
    Account,
    AccountStatus,
    IdempotencyKey,
    KYCStatus,
    LedgerDirection,
    LedgerEntry,
    Transfer,
    TransferStatus,
    User,
)
from app.services.transfer import transfer


def create_test_accounts(
    db,
    sender_balance=Decimal("10000.00"),
    receiver_balance=Decimal("5000.00"),
):
    sender_user = User(
        full_name="Transfer Sender",
        email=f"sender-{uuid4().hex}@test.godandbank.local",
        phone=f"+23480{uuid4().int % 10_000_000:07d}",
        password_hash="test_hash",
        kyc_status=KYCStatus.VERIFIED,
        terms_accepted_at=datetime.now(UTC),
    )

    receiver_user = User(
        full_name="Transfer Receiver",
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
        db.query(IdempotencyKey).filter(
            IdempotencyKey.user_id.in_(user_ids)
        ).delete(synchronize_session=False)


def test_transfer_moves_money_and_creates_ledger_entries():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        result = transfer(
            db=db,
            user_id=sender_user.id,
            idempotency_key=f"transfer-{uuid4().hex}",
            sender_account_number=sender_account.account_number,
            receiver_account_number=receiver_account.account_number,
            amount=Decimal("3000.00"),
            currency="NGN",
        )

        db.refresh(sender_account)
        db.refresh(receiver_account)

        assert sender_account.balance == Decimal("7000.00")
        assert receiver_account.balance == Decimal("8000.00")

        assert result.status.value == "success"
        assert result.amount == Decimal("3000.00")
        assert result.sender_account_id == sender_account.id
        assert result.receiver_account_id == receiver_account.id
        assert result.reference.startswith("TRF-")

        entries = (
            db.query(LedgerEntry)
            .filter(LedgerEntry.transfer_id == result.id)
            .all()
        )

        assert len(entries) == 2

        debit = next(
            entry
            for entry in entries
            if entry.direction == LedgerDirection.DEBIT
        )

        credit = next(
            entry
            for entry in entries
            if entry.direction == LedgerDirection.CREDIT
        )

        assert debit.amount == Decimal("3000.00")
        assert debit.balance_after == Decimal("7000.00")
        assert debit.account_id == sender_account.id

        assert credit.amount == Decimal("3000.00")
        assert credit.balance_after == Decimal("8000.00")
        assert credit.account_id == receiver_account.id

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        if sender_user:
            db.delete(sender_user)

        if receiver_user:
            db.delete(receiver_user)

        db.commit()
        db.close()


def test_multiple_transfers_reconcile_with_ledger_balances():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        first_transfer = transfer(
            db=db,
            user_id=sender_user.id,
            idempotency_key=f"reconcile-transfer-{uuid4().hex}",
            sender_account_number=sender_account.account_number,
            receiver_account_number=receiver_account.account_number,
            amount=Decimal("1000.00"),
            currency="NGN",
        )

        second_transfer = transfer(
            db=db,
            user_id=sender_user.id,
            idempotency_key=f"reconcile-transfer-{uuid4().hex}",
            sender_account_number=sender_account.account_number,
            receiver_account_number=receiver_account.account_number,
            amount=Decimal("500.00"),
            currency="NGN",
        )

        db.refresh(sender_account)
        db.refresh(receiver_account)

        sender_entries = (
            db.query(LedgerEntry)
            .filter(LedgerEntry.account_id == sender_account.id)
            .order_by(LedgerEntry.created_at.asc(), LedgerEntry.id.asc())
            .all()
        )

        receiver_entries = (
            db.query(LedgerEntry)
            .filter(LedgerEntry.account_id == receiver_account.id)
            .order_by(LedgerEntry.created_at.asc(), LedgerEntry.id.asc())
            .all()
        )

        assert len(sender_entries) == 2
        assert len(receiver_entries) == 2

        assert sender_entries[0].transfer_id == first_transfer.id
        assert sender_entries[0].direction == LedgerDirection.DEBIT
        assert sender_entries[0].amount == Decimal("1000.00")
        assert sender_entries[0].balance_after == Decimal("9000.00")

        assert sender_entries[1].transfer_id == second_transfer.id
        assert sender_entries[1].direction == LedgerDirection.DEBIT
        assert sender_entries[1].amount == Decimal("500.00")
        assert sender_entries[1].balance_after == Decimal("8500.00")

        assert receiver_entries[0].transfer_id == first_transfer.id
        assert receiver_entries[0].direction == LedgerDirection.CREDIT
        assert receiver_entries[0].amount == Decimal("1000.00")
        assert receiver_entries[0].balance_after == Decimal("6000.00")

        assert receiver_entries[1].transfer_id == second_transfer.id
        assert receiver_entries[1].direction == LedgerDirection.CREDIT
        assert receiver_entries[1].amount == Decimal("500.00")
        assert receiver_entries[1].balance_after == Decimal("6500.00")

        assert sender_account.balance == sender_entries[-1].balance_after
        assert receiver_account.balance == receiver_entries[-1].balance_after

        assert sender_account.balance == Decimal("8500.00")
        assert receiver_account.balance == Decimal("6500.00")

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        if sender_user:
            db.delete(sender_user)

        if receiver_user:
            db.delete(receiver_user)

        db.commit()
        db.close()


def test_transfer_rolls_back_when_balance_is_insufficient():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(
            db,
            sender_balance=Decimal("1000.00"),
        )

        with pytest.raises(
            ValueError,
            match="Insufficient balance",
        ):
            transfer(
                db=db,
                user_id=sender_user.id,
                idempotency_key=f"insufficient-{uuid4().hex}",
                sender_account_number=sender_account.account_number,
                receiver_account_number=receiver_account.account_number,
                amount=Decimal("2000.00"),
                currency="NGN",
            )

        db.refresh(sender_account)
        db.refresh(receiver_account)

        assert sender_account.balance == Decimal("1000.00")
        assert receiver_account.balance == Decimal("5000.00")

        assert (
            db.query(Transfer)
            .filter(
                Transfer.sender_account_id == sender_account.id
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

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        if sender_user:
            db.delete(sender_user)

        if receiver_user:
            db.delete(receiver_user)

        db.commit()
        db.close()


def test_transfer_rejects_zero_amount():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        with pytest.raises(
            ValueError,
            match="Transfer amount must be greater than zero",
        ):
            transfer(
                db=db,
                user_id=sender_user.id,
                idempotency_key=f"zero-{uuid4().hex}",
                sender_account_number=sender_account.account_number,
                receiver_account_number=receiver_account.account_number,
                amount=Decimal("0.00"),
                currency="NGN",
            )

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        if sender_user:
            db.delete(sender_user)

        if receiver_user:
            db.delete(receiver_user)

        db.commit()
        db.close()


def test_transfer_rejects_self_transfer():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        with pytest.raises(
            ValueError,
            match="Sender and receiver accounts must be different",
        ):
            transfer(
                db=db,
                user_id=sender_user.id,
                idempotency_key=f"self-{uuid4().hex}",
                sender_account_number=sender_account.account_number,
                receiver_account_number=sender_account.account_number,
                amount=Decimal("100.00"),
                currency="NGN",
            )

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        if sender_user:
            db.delete(sender_user)

        if receiver_user:
            db.delete(receiver_user)

        db.commit()
        db.close()


def test_transfer_rejects_frozen_sender():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        sender_account.status = AccountStatus.FROZEN
        db.commit()

        with pytest.raises(
            ValueError,
            match="Sender account is not active",
        ):
            transfer(
                db=db,
                user_id=sender_user.id,
                idempotency_key=f"frozen-{uuid4().hex}",
                sender_account_number=sender_account.account_number,
                receiver_account_number=receiver_account.account_number,
                amount=Decimal("100.00"),
                currency="NGN",
            )

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        if sender_user:
            db.delete(sender_user)

        if receiver_user:
            db.delete(receiver_user)

        db.commit()
        db.close()


def test_transfer_rejects_currency_mismatch():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        with pytest.raises(
            ValueError,
            match="Sender account currency does not match transfer currency",
        ):
            transfer(
                db=db,
                user_id=sender_user.id,
                idempotency_key=f"currency-{uuid4().hex}",
                sender_account_number=sender_account.account_number,
                receiver_account_number=receiver_account.account_number,
                amount=Decimal("100.00"),
                currency="USD",
            )

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        if sender_user:
            db.delete(sender_user)

        if receiver_user:
            db.delete(receiver_user)

        db.commit()
        db.close()


def test_transfer_returns_existing_transfer_for_duplicate_request():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        key = f"duplicate-{uuid4().hex}"

        first = transfer(
            db=db,
            user_id=sender_user.id,
            idempotency_key=key,
            sender_account_number=sender_account.account_number,
            receiver_account_number=receiver_account.account_number,
            amount=Decimal("500.00"),
            currency="NGN",
        )

        second = transfer(
            db=db,
            user_id=sender_user.id,
            idempotency_key=key,
            sender_account_number=sender_account.account_number,
            receiver_account_number=receiver_account.account_number,
            amount=Decimal("500.00"),
            currency="NGN",
        )

        db.refresh(sender_account)
        db.refresh(receiver_account)

        assert first.id == second.id
        assert first.reference == second.reference

        assert sender_account.balance == Decimal("9500.00")
        assert receiver_account.balance == Decimal("5500.00")

        assert (
            db.query(Transfer)
            .filter(Transfer.idempotency_key == key)
            .count()
            == 1
        )

        assert (
            db.query(LedgerEntry)
            .filter(LedgerEntry.transfer_id == first.id)
            .count()
            == 2
        )

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        if sender_user:
            db.delete(sender_user)

        if receiver_user:
            db.delete(receiver_user)

        db.commit()
        db.close()


def test_transfer_rejects_idempotency_key_conflict():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        key = f"conflict-{uuid4().hex}"

        transfer(
            db=db,
            user_id=sender_user.id,
            idempotency_key=key,
            sender_account_number=sender_account.account_number,
            receiver_account_number=receiver_account.account_number,
            amount=Decimal("500.00"),
            currency="NGN",
        )

        with pytest.raises(
            ValueError,
            match="Idempotency key was already used with a different request",
        ):
            transfer(
                db=db,
                user_id=sender_user.id,
                idempotency_key=key,
                sender_account_number=sender_account.account_number,
                receiver_account_number=receiver_account.account_number,
                amount=Decimal("600.00"),
                currency="NGN",
            )

        db.refresh(sender_account)
        db.refresh(receiver_account)

        assert sender_account.balance == Decimal("9500.00")
        assert receiver_account.balance == Decimal("5500.00")

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [sender_user, receiver_user],
            sender_account,
            receiver_account,
        )

        if sender_user:
            db.delete(sender_user)

        if receiver_user:
            db.delete(receiver_user)

        db.commit()
        db.close()
        

def test_transfer_creates_audit_log():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender = None
    receiver = None
    result = None

    try:
        sender_user = User(
            full_name="Audit Sender",
            email=f"audit-sender-{uuid4()}@godandbank.local",
            phone=f"+23480{uuid4().int % 10**9:09d}",
            password_hash="test_hash",
            kyc_status=KYCStatus.VERIFIED,
            terms_accepted_at=datetime.now(UTC),
        )

        receiver_user = User(
            full_name="Audit Receiver",
            email=f"audit-receiver-{uuid4()}@godandbank.local",
            phone=f"+23481{uuid4().int % 10**9:09d}",
            password_hash="test_hash",
            kyc_status=KYCStatus.VERIFIED,
            terms_accepted_at=datetime.now(UTC),
        )

        db.add_all([sender_user, receiver_user])
        db.flush()

        sender = Account(
            user_id=sender_user.id,
            account_number=f"{uuid4().int % 10**10:010d}",
            balance=Decimal("1000.00"),
            currency="NGN",
            status=AccountStatus.ACTIVE,
        )

        receiver = Account(
            user_id=receiver_user.id,
            account_number=f"{uuid4().int % 10**10:010d}",
            balance=Decimal("500.00"),
            currency="NGN",
            status=AccountStatus.ACTIVE,
        )

        db.add_all([sender, receiver])
        db.flush()

        result = transfer(
            db=db,
            user_id=sender_user.id,
            idempotency_key=f"audit-transfer-{uuid4()}",
            sender_account_number=sender.account_number,
            receiver_account_number=receiver.account_number,
            amount=Decimal("100.00"),
            currency="NGN",
            ip_address="192.168.1.10",
        )

        audit_log = (
            db.query(AuditLog)
            .filter(AuditLog.action == "transfer.created")
            .order_by(AuditLog.created_at.desc())
            .first()
        )

        assert result.status == TransferStatus.SUCCESS
        assert audit_log is not None
        assert audit_log.actor_user_id == sender_user.id
        assert str(audit_log.ip_address) == "192.168.1.10"
        assert audit_log.metadata_json["reference"] == result.reference
        assert audit_log.metadata_json["amount"] == "100.00"
        assert audit_log.metadata_json["currency"] == "NGN"
        assert audit_log.metadata_json["status"] == "success"

    finally:
        db.rollback()

        if result is not None:
            db.query(AuditLog).filter(
                AuditLog.metadata_json["reference"].as_string() == result.reference
            ).delete(synchronize_session=False)

            db.query(LedgerEntry).filter(
                LedgerEntry.transfer_id == result.id
            ).delete(synchronize_session=False)

            db.query(Transfer).filter(
                Transfer.id == result.id
            ).delete(synchronize_session=False)

        db.query(IdempotencyKey).filter(
            IdempotencyKey.key.like("audit-transfer-%")
        ).delete(synchronize_session=False)

        if sender is not None and sender.id:
            db.query(Account).filter(Account.id == sender.id).delete(
                synchronize_session=False
            )

        if receiver is not None and receiver.id:
            db.query(Account).filter(Account.id == receiver.id).delete(
                synchronize_session=False
            )

        if sender_user is not None and sender_user.id:
            db.query(User).filter(User.id == sender_user.id).delete(
                synchronize_session=False
            )

        if receiver_user is not None and receiver_user.id:
            db.query(User).filter(User.id == receiver_user.id).delete(
                synchronize_session=False
            )

        db.commit()
        db.close()
