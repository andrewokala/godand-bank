from datetime import UTC, datetime
from decimal import Decimal

from app.db.session import SessionLocal
from app.models import User, TransferStatus
from app.repositories.account import create_account
from app.repositories.transfer import (
    create_transfer,
    get_transfer_by_id,
    get_transfer_by_reference,
    get_transfers_by_account_ids,
    get_transfers_by_account_id,
)


def test_get_transfers_by_account_ids_filters_and_paginates():
    db = SessionLocal()

    user_a_email = "repo-history-a@test.godandbank.local"
    user_b_email = "repo-history-b@test.godandbank.local"
    user_c_email = "repo-history-c@test.godandbank.local"
    user_d_email = "repo-history-d@test.godandbank.local"

    account_a_number = "7654321001"
    account_b_number = "7654321002"
    account_c_number = "7654321003"
    account_d_number = "7654321004"

    try:
        user_a = User(
            full_name="Repository History A",
            email=user_a_email,
            phone="+2348012345101",
            password_hash="test_hash",
            terms_accepted_at=datetime.now(UTC),
        )

        user_b = User(
            full_name="Repository History B",
            email=user_b_email,
            phone="+2348012345102",
            password_hash="test_hash",
            terms_accepted_at=datetime.now(UTC),
        )

        user_c = User(
            full_name="Repository History C",
            email=user_c_email,
            phone="+2348012345103",
            password_hash="test_hash",
            terms_accepted_at=datetime.now(UTC),
        )

        user_d = User(
            full_name="Repository History D",
            email=user_d_email,
            phone="+2348012345104",
            password_hash="test_hash",
            terms_accepted_at=datetime.now(UTC),
        )

        db.add_all([user_a, user_b, user_c, user_d])
        db.commit()

        db.refresh(user_a)
        db.refresh(user_b)
        db.refresh(user_c)
        db.refresh(user_d)

        account_a = create_account(
            db=db,
            user_id=user_a.id,
            account_number=account_a_number,
        )

        account_b = create_account(
            db=db,
            user_id=user_b.id,
            account_number=account_b_number,
        )

        account_c = create_account(
            db=db,
            user_id=user_c.id,
            account_number=account_c_number,
        )

        account_d = create_account(
            db=db,
            user_id=user_d.id,
            account_number=account_d_number,
        )

        first_transfer = create_transfer(
            db=db,
            sender_account_id=account_a.id,
            receiver_account_id=account_b.id,
            amount=Decimal("100.00"),
            reference="TRF-REPO-HISTORY-001",
        )

        second_transfer = create_transfer(
            db=db,
            sender_account_id=account_b.id,
            receiver_account_id=account_a.id,
            amount=Decimal("200.00"),
            reference="TRF-REPO-HISTORY-002",
        )

        unrelated_transfer = create_transfer(
            db=db,
            sender_account_id=account_c.id,
            receiver_account_id=account_d.id,
            amount=Decimal("300.00"),
            reference="TRF-REPO-HISTORY-003",
        )

        first_transfer.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        second_transfer.created_at = datetime(2026, 1, 2, tzinfo=UTC)
        unrelated_transfer.created_at = datetime(2026, 1, 3, tzinfo=UTC)

        db.commit()

        first_page, total = get_transfers_by_account_ids(
            db=db,
            account_ids=[account_a.id, account_b.id],
            limit=1,
            offset=0,
        )

        second_page, second_total = get_transfers_by_account_ids(
            db=db,
            account_ids=[account_a.id, account_b.id],
            limit=1,
            offset=1,
        )

        assert total == 2
        assert second_total == 2

        assert len(first_page) == 1
        assert len(second_page) == 1

        assert first_page[0].id == second_transfer.id
        assert second_page[0].id == first_transfer.id

        assert unrelated_transfer.id not in {
            first_page[0].id,
            second_page[0].id,
        }

    finally:
        if "unrelated_transfer" in locals() and unrelated_transfer.id is not None:
            db.delete(unrelated_transfer)

        if "second_transfer" in locals() and second_transfer.id is not None:
            db.delete(second_transfer)

        if "first_transfer" in locals() and first_transfer.id is not None:
            db.delete(first_transfer)

        if "account_d" in locals() and account_d.id is not None:
            db.delete(account_d)

        if "account_c" in locals() and account_c.id is not None:
            db.delete(account_c)

        if "account_b" in locals() and account_b.id is not None:
            db.delete(account_b)

        if "account_a" in locals() and account_a.id is not None:
            db.delete(account_a)

        if "user_d" in locals() and user_d.id is not None:
            db.delete(user_d)

        if "user_c" in locals() and user_c.id is not None:
            db.delete(user_c)

        if "user_b" in locals() and user_b.id is not None:
            db.delete(user_b)

        if "user_a" in locals() and user_a.id is not None:
            db.delete(user_a)

        db.commit()
        db.close()


def test_transfer_repository():
    db = SessionLocal()

    sender_email = "sender-transfer@test.godandbank.local"
    receiver_email = "receiver-transfer@test.godandbank.local"

    sender_account_number = "7654321098"
    receiver_account_number = "6543210987"

    reference = "TRF-REPO-001"
    idempotency_key = "repo-transfer-test-001"

    try:
        sender = User(
            full_name="Sender Test",
            email=sender_email,
            phone="+2348012345004",
            password_hash="test_hash",
            terms_accepted_at=datetime.now(UTC),
        )

        receiver = User(
            full_name="Receiver Test",
            email=receiver_email,
            phone="+2348012345005",
            password_hash="test_hash",
            terms_accepted_at=datetime.now(UTC),
        )

        db.add_all([sender, receiver])
        db.commit()
        db.refresh(sender)
        db.refresh(receiver)

        sender_account = create_account(
            db=db,
            user_id=sender.id,
            account_number=sender_account_number,
        )

        receiver_account = create_account(
            db=db,
            user_id=receiver.id,
            account_number=receiver_account_number,
        )

        transfer = create_transfer(
            db=db,
            sender_account_id=sender_account.id,
            receiver_account_id=receiver_account.id,
            amount=Decimal("2500.00"),
            reference=reference,
            currency="NGN",
            idempotency_key=idempotency_key,
            status=TransferStatus.SUCCESS,
        )

        assert transfer.id is not None
        assert transfer.sender_account_id == sender_account.id
        assert transfer.receiver_account_id == receiver_account.id
        assert transfer.amount == Decimal("2500.00")
        assert transfer.currency == "NGN"
        assert transfer.reference == reference
        assert transfer.idempotency_key == idempotency_key
        assert transfer.status == TransferStatus.SUCCESS

        saved_by_id = get_transfer_by_id(
            db=db,
            transfer_id=transfer.id,
        )

        assert saved_by_id is not None
        assert saved_by_id.reference == reference

        saved_by_reference = get_transfer_by_reference(
            db=db,
            reference=reference,
        )

        assert saved_by_reference is not None
        assert saved_by_reference.id == transfer.id

        sender_transfers = get_transfers_by_account_id(
            db=db,
            account_id=sender_account.id,
        )

        receiver_transfers = get_transfers_by_account_id(
            db=db,
            account_id=receiver_account.id,
        )

        assert len(sender_transfers) == 1
        assert sender_transfers[0].id == transfer.id

        assert len(receiver_transfers) == 1
        assert receiver_transfers[0].id == transfer.id

    finally:
        if "transfer" in locals() and transfer.id is not None:
            db.delete(transfer)

        if "receiver_account" in locals() and receiver_account.id is not None:
            db.delete(receiver_account)

        if "sender_account" in locals() and sender_account.id is not None:
            db.delete(sender_account)

        if "receiver" in locals() and receiver.id is not None:
            db.delete(receiver)

        if "sender" in locals() and sender.id is not None:
            db.delete(sender)

        db.commit()
        db.close()
