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
    sender_balance=Decimal("1000.00"),
    receiver_balance=Decimal("5000.00"),
):
    sender_user = User(
        full_name="Concurrent Sender",
        email=f"sender-{uuid4().hex}@test.godandbank.local",
        phone=f"+23480{uuid4().int % 10_000_000:07d}",
        password_hash="test_hash",
        kyc_status=KYCStatus.VERIFIED,
        terms_accepted_at=datetime.now(UTC),
    )

    receiver_user = User(
        full_name="Concurrent Receiver",
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
    sender_account_number,
    receiver_account_number,
    amount,
):
    db = SessionLocal()

    try:
        return transfer(
            db=db,
            user_id=user_id,
            idempotency_key=f"concurrency-{uuid4().hex}",
            sender_account_number=sender_account_number,
            receiver_account_number=receiver_account_number,
            amount=amount,
            currency="NGN",
        )
    except Exception as exc:
        return exc
    finally:
        db.close()


def test_concurrent_transfers_are_serialized():
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
            receiver_balance=Decimal("5000.00"),
        )

        amount = Decimal("100.00")

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    run_transfer,
                    sender_user.id,
                    sender_account.account_number,
                    receiver_account.account_number,
                    amount,
                )
                for _ in range(2)
            ]

            results = [
                future.result()
                for future in futures
            ]

        db.expire_all()

        db.refresh(sender_account)
        db.refresh(receiver_account)

        assert sender_account.balance == Decimal("800.00")
        assert receiver_account.balance == Decimal("5200.00")

        successful_results = [
            result
            for result in results
            if isinstance(result, Transfer)
        ]

        failures = [
            result
            for result in results
            if isinstance(result, Exception)
        ]

        assert len(successful_results) == 2
        assert len(failures) == 0

        transfer_count = (
            db.query(Transfer)
            .filter(
                Transfer.sender_account_id == sender_account.id,
                Transfer.receiver_account_id == receiver_account.id,
            )
            .count()
        )

        assert transfer_count == 2

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


def test_concurrent_transfers_cannot_overdraw_account():
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
            receiver_balance=Decimal("5000.00"),
        )

        amount = Decimal("700.00")

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    run_transfer,
                    sender_user.id,
                    sender_account.account_number,
                    receiver_account.account_number,
                    amount,
                )
                for _ in range(2)
            ]

            results = [
                future.result()
                for future in futures
            ]

        db.expire_all()

        db.refresh(sender_account)
        db.refresh(receiver_account)

        successful_results = [
            result
            for result in results
            if isinstance(result, Transfer)
        ]

        failures = [
            result
            for result in results
            if isinstance(result, Exception)
        ]

        assert len(successful_results) == 1
        assert len(failures) == 1

        assert isinstance(failures[0], ValueError)
        assert str(failures[0]) == "Insufficient balance."

        assert sender_account.balance == Decimal("300.00")
        assert receiver_account.balance == Decimal("5700.00")

        transfer_count = (
            db.query(Transfer)
            .filter(
                Transfer.sender_account_id == sender_account.id,
                Transfer.receiver_account_id == receiver_account.id,
            )
            .count()
        )

        assert transfer_count == 1

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

def test_opposite_direction_transfers_do_not_deadlock():
    db = SessionLocal()

    first_user = None
    second_user = None
    first_account = None
    second_account = None

    try:
        (
            first_user,
            second_user,
            first_account,
            second_account,
        ) = create_test_accounts(
            db,
            sender_balance=Decimal("1000.00"),
            receiver_balance=Decimal("1000.00"),
        )

        amount = Decimal("100.00")

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_transfer = executor.submit(
                run_transfer,
                first_user.id,
                first_account.account_number,
                second_account.account_number,
                amount,
            )

            second_transfer = executor.submit(
                run_transfer,
                second_user.id,
                second_account.account_number,
                first_account.account_number,
                amount,
            )

            results = [
                first_transfer.result(),
                second_transfer.result(),
            ]

        db.expire_all()

        db.refresh(first_account)
        db.refresh(second_account)

        successful_results = [
            result
            for result in results
            if isinstance(result, Transfer)
        ]

        failures = [
            result
            for result in results
            if isinstance(result, Exception)
        ]

        assert len(successful_results) == 2
        assert len(failures) == 0

        assert first_account.balance == Decimal("1000.00")
        assert second_account.balance == Decimal("1000.00")

        transfer_count = db.query(Transfer).filter(
            (
                (Transfer.sender_account_id == first_account.id)
                & (Transfer.receiver_account_id == second_account.id)
            )
            |
            (
                (Transfer.sender_account_id == second_account.id)
                & (Transfer.receiver_account_id == first_account.id)
            )
        ).count()

        assert transfer_count == 2

    finally:
        db.rollback()

        cleanup_accounts(
            db,
            [first_user, second_user],
            first_account,
            second_account,
        )

        db.commit()
        db.close()
