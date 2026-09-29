from datetime import UTC, datetime
from decimal import Decimal

from app.db.session import SessionLocal
from app.models import (
    Account,
    IdempotencyKey,
    LedgerDirection,
    LedgerEntry,
    Transfer,
    TransferStatus,
    User,
)
from app.repositories.ledger_entry import get_ledger_entries_by_account_id


def test_get_ledger_entries_by_account_id_filters_counts_and_paginates():
    db = SessionLocal()

    users = []
    accounts = []
    transfers = []
    entries = []

    try:
        users = [
            User(
                full_name="Ledger User One",
                email="ledger-user-one@test.godandbank.local",
                phone="+2348012399101",
                password_hash="test_hash",
                terms_accepted_at=datetime.now(UTC),
            ),
            User(
                full_name="Ledger User Two",
                email="ledger-user-two@test.godandbank.local",
                phone="+2348012399102",
                password_hash="test_hash",
                terms_accepted_at=datetime.now(UTC),
            ),
            User(
                full_name="Ledger User Three",
                email="ledger-user-three@test.godandbank.local",
                phone="+2348012399103",
                password_hash="test_hash",
                terms_accepted_at=datetime.now(UTC),
            ),
        ]

        db.add_all(users)
        db.commit()

        accounts = [
            Account(
                user_id=users[0].id,
                account_number="2000000001",
                balance=Decimal("9700.00"),
                currency="NGN",
            ),
            Account(
                user_id=users[1].id,
                account_number="2000000002",
                balance=Decimal("5300.00"),
                currency="NGN",
            ),
            Account(
                user_id=users[2].id,
                account_number="2000000003",
                balance=Decimal("10000.00"),
                currency="NGN",
            ),
        ]

        db.add_all(accounts)
        db.commit()

        transfers = [
            Transfer(
                reference="LEDGER-TEST-001",
                sender_account_id=accounts[0].id,
                receiver_account_id=accounts[1].id,
                amount=Decimal("100.00"),
                currency="NGN",
                status=TransferStatus.SUCCESS,
                idempotency_key="ledger-test-key-001",
                created_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            ),
            Transfer(
                reference="LEDGER-TEST-002",
                sender_account_id=accounts[0].id,
                receiver_account_id=accounts[1].id,
                amount=Decimal("200.00"),
                currency="NGN",
                status=TransferStatus.SUCCESS,
                idempotency_key="ledger-test-key-002",
                created_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
            ),
            Transfer(
                reference="LEDGER-TEST-003",
                sender_account_id=accounts[2].id,
                receiver_account_id=accounts[1].id,
                amount=Decimal("300.00"),
                currency="NGN",
                status=TransferStatus.SUCCESS,
                idempotency_key="ledger-test-key-003",
                created_at=datetime(2026, 1, 3, 10, 0, tzinfo=UTC),
            ),
        ]

        db.add_all(transfers)
        db.commit()

        entries = [
            LedgerEntry(
                transfer_id=transfers[0].id,
                account_id=accounts[0].id,
                direction=LedgerDirection.DEBIT,
                amount=Decimal("100.00"),
                balance_after=Decimal("9900.00"),
                created_at=datetime(2026, 1, 1, 10, 1, tzinfo=UTC),
            ),
            LedgerEntry(
                transfer_id=transfers[1].id,
                account_id=accounts[0].id,
                direction=LedgerDirection.DEBIT,
                amount=Decimal("200.00"),
                balance_after=Decimal("9700.00"),
                created_at=datetime(2026, 1, 2, 10, 1, tzinfo=UTC),
            ),
            LedgerEntry(
                transfer_id=transfers[2].id,
                account_id=accounts[0].id,
                direction=LedgerDirection.CREDIT,
                amount=Decimal("300.00"),
                balance_after=Decimal("10000.00"),
                created_at=datetime(2026, 1, 3, 10, 1, tzinfo=UTC),
            ),
            LedgerEntry(
                transfer_id=transfers[2].id,
                account_id=accounts[2].id,
                direction=LedgerDirection.DEBIT,
                amount=Decimal("300.00"),
                balance_after=Decimal("9700.00"),
                created_at=datetime(2026, 1, 3, 10, 2, tzinfo=UTC),
            ),
        ]

        db.add_all(entries)
        db.commit()

        page, total = get_ledger_entries_by_account_id(
            db=db,
            account_id=accounts[0].id,
            limit=2,
            offset=0,
        )

        assert total == 3
        assert len(page) == 2
        assert [entry.id for entry in page] == [
            entries[2].id,
            entries[1].id,
        ]
        assert all(
            entry.account_id == accounts[0].id
            for entry in page
        )

        next_page, next_total = get_ledger_entries_by_account_id(
            db=db,
            account_id=accounts[0].id,
            limit=2,
            offset=2,
        )

        assert next_total == 3
        assert len(next_page) == 1
        assert next_page[0].id == entries[0].id
        assert next_page[0].account_id == accounts[0].id

    finally:
        db.rollback()

        if entries:
            db.query(LedgerEntry).filter(
                LedgerEntry.id.in_([entry.id for entry in entries])
            ).delete(synchronize_session=False)

        if transfers:
            db.query(Transfer).filter(
                Transfer.id.in_([transfer.id for transfer in transfers])
            ).delete(synchronize_session=False)

        if users:
            user_ids = [user.id for user in users]

            db.query(IdempotencyKey).filter(
                IdempotencyKey.user_id.in_(user_ids)
            ).delete(synchronize_session=False)

            db.query(Account).filter(
                Account.user_id.in_(user_ids)
            ).delete(synchronize_session=False)

            db.query(User).filter(
                User.id.in_(user_ids)
            ).delete(synchronize_session=False)

        db.commit()
        db.close()
