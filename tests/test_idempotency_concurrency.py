from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.db.session import SessionLocal
from app.models import (
    Account,
    AccountStatus,
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
        full_name="Idempotency Sender",
        email=f"sender-{uuid4().hex}@test.godandbank.local",
        phone=f"+23480{uuid4().int % 10_000_000:07d}",
        password_hash="test_hash",
        kyc_status=KYCStatus.VERIFIED,
        terms_accepted_at=datetime.now(UTC),
    )

    receiver_user = User(
        full_name="Idempotency Receiver",
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

        db.query(User).filter(
            User.id.in_(user_ids)
        ).delete(synchronize_session=False)


def run_transfer(
    user_id,
    idempotency_key,
    sender_account_number,
    receiver_account_number,
):
    db = SessionLocal()

    try:
        return transfer(
            db=db,
            user_id=user_id,
            idempotency_key=idempotency_key,
            sender_account_number=sender_account_number,
            receiver_account_number=receiver_account_number,
            amount=Decimal("100.00"),
            currency="NGN",
        )
    finally:
        db.close()


def test_concurrent_same_idempotency_key_creates_only_one_transfer():
    db = SessionLocal()

    sender_user = None
    receiver_user = None
    sender_account = None
    receiver_account = None

    idempotency_key = f"same-key-{uuid4().hex}"

    try:
        (
            sender_user,
            receiver_user,
            sender_account,
            receiver_account,
        ) = create_test_accounts(db)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    run_transfer,
                    sender_user.id,
                    idempotency_key,
                    sender_account.account_number,
                    receiver_account.account_number,
                )
                for _ in range(2)
            ]

            results = [future.result() for future in futures]

        assert len(results) == 2
        assert results[0].id == results[1].id
        assert results[0].reference == results[1].reference

        db.refresh(sender_account)
        db.refresh(receiver_account)

        assert sender_account.balance == Decimal("9900.00")
        assert receiver_account.balance == Decimal("5100.00")

        assert (
            db.query(Transfer)
            .filter(
                Transfer.sender_account_id == sender_account.id,
                Transfer.receiver_account_id == receiver_account.id,
                Transfer.idempotency_key == idempotency_key,
            )
            .count()
            == 1
        )

        assert (
            db.query(LedgerEntry)
            .filter(
                LedgerEntry.account_id.in_(
                    [sender_account.id, receiver_account.id]
                )
            )
            .count()
            == 2
        )

        assert (
            db.query(IdempotencyKey)
            .filter(
                IdempotencyKey.key == idempotency_key
            )
            .count()
            == 1
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