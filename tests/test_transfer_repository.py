from datetime import UTC, datetime
from decimal import Decimal

from app.db.session import SessionLocal
from app.models import User, TransferStatus
from app.repositories.account import create_account
from app.repositories.transfer import (
    create_transfer,
    get_transfer_by_id,
    get_transfer_by_reference,
    get_transfers_by_account_id,
)


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
