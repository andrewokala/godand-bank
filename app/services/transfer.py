from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AccountStatus,
    IdempotencyKey,
    LedgerDirection,
    LedgerEntry,
    Transfer,
    TransferStatus,
)
from app.repositories.account import get_account_by_number_for_update
from app.repositories.idempotency import (
    get_idempotency_key,
    reserve_idempotency_key,
    store_response_snapshot,
)
from app.services.idempotency import build_transfer_request_hash
from app.services.transfer_response import build_transfer_response_snapshot


def transfer(
    db: Session,
    user_id: UUID,
    idempotency_key: str,
    sender_account_number: str,
    receiver_account_number: str,
    amount: Decimal,
    currency: str = "NGN",
    note: str | None = None,
) -> Transfer:
    if not idempotency_key:
        raise ValueError("Idempotency key is required.")

    if amount <= Decimal("0.00"):
        raise ValueError("Transfer amount must be greater than zero.")

    if sender_account_number == receiver_account_number:
        raise ValueError(
            "Sender and receiver accounts must be different."
        )

    request_hash = build_transfer_request_hash(
        user_id=user_id,
        sender_account_number=sender_account_number,
        receiver_account_number=receiver_account_number,
        amount=amount,
        currency=currency,
        note=note,
    )

    try:
        existing_key = get_idempotency_key(
            db=db,
            key=idempotency_key,
        )

        if existing_key is not None:
            if existing_key.user_id != user_id:
                raise ValueError(
                    "Idempotency key belongs to another user."
                )

            if existing_key.request_hash != request_hash:
                raise ValueError(
                    "Idempotency key was already used with a different request."
                )

            if not existing_key.response_snapshot:
                raise ValueError(
                    "Idempotency key is already reserved."
                )

            transfer_id = existing_key.response_snapshot.get("id")

            if transfer_id is None:
                raise ValueError(
                    "Stored idempotency response is invalid."
                )

            transfer_record = db.get(
                Transfer,
                UUID(transfer_id),
            )

            if transfer_record is None:
                raise ValueError(
                    "Stored transfer response could not be found."
                )

            return transfer_record

        reserve_idempotency_key(
            db=db,
            key=idempotency_key,
            user_id=user_id,
            request_hash=request_hash,
        )

        # Lock accounts in deterministic order.
        #
        # This prevents opposite-direction transfers from acquiring
        # the same locks in different orders.
        account_numbers = sorted(
            [sender_account_number, receiver_account_number]
        )

        accounts = {}

        for account_number in account_numbers:
            account = get_account_by_number_for_update(
                db=db,
                account_number=account_number,
            )

            if account is None:
                raise ValueError(
                    f"Account {account_number} not found."
                )

            accounts[account_number] = account

        sender = accounts[sender_account_number]
        receiver = accounts[receiver_account_number]

        if sender.status != AccountStatus.ACTIVE:
            raise ValueError("Sender account is not active.")

        if receiver.status != AccountStatus.ACTIVE:
            raise ValueError("Receiver account is not active.")

        if sender.currency != currency:
            raise ValueError(
                "Sender account currency does not match transfer currency."
            )

        if receiver.currency != currency:
            raise ValueError(
                "Receiver account currency does not match transfer currency."
            )

        if sender.balance < amount:
            raise ValueError("Insufficient balance.")

        sender.balance -= amount
        sender.version += 1

        receiver.balance += amount
        receiver.version += 1

        reference = f"TRF-{uuid4().hex[:12].upper()}"

        transfer_record = Transfer(
            reference=reference,
            sender_account_id=sender.id,
            receiver_account_id=receiver.id,
            amount=amount,
            currency=currency,
            note=note,
            status=TransferStatus.SUCCESS,
            idempotency_key=idempotency_key,
        )

        db.add(transfer_record)
        db.flush()

        sender_entry = LedgerEntry(
            transfer_id=transfer_record.id,
            account_id=sender.id,
            direction=LedgerDirection.DEBIT,
            amount=amount,
            balance_after=sender.balance,
        )

        receiver_entry = LedgerEntry(
            transfer_id=transfer_record.id,
            account_id=receiver.id,
            direction=LedgerDirection.CREDIT,
            amount=amount,
            balance_after=receiver.balance,
        )

        db.add(sender_entry)
        db.add(receiver_entry)

        db.flush()

        response_snapshot = build_transfer_response_snapshot(
            transfer_record
        )

        idempotency_record = get_idempotency_key(
            db=db,
            key=idempotency_key,
        )

        if idempotency_record is None:
            raise ValueError(
                "Idempotency key reservation was lost."
            )

        store_response_snapshot(
            idempotency_record,
            response_snapshot,
        )

        db.commit()
        db.refresh(transfer_record)

        return transfer_record

    except IntegrityError:
        db.rollback()

        existing_key = get_idempotency_key(
            db=db,
            key=idempotency_key,
        )

        if existing_key is None:
            raise

        if existing_key.user_id != user_id:
            raise ValueError(
                "Idempotency key belongs to another user."
            )

        if existing_key.request_hash != request_hash:
            raise ValueError(
                "Idempotency key was already used with a different request."
            )

        if not existing_key.response_snapshot:
            raise ValueError(
                "Idempotency key is already reserved."
            )

        transfer_id = existing_key.response_snapshot.get("id")

        if transfer_id is None:
            raise ValueError(
                "Stored idempotency response is invalid."
            )

        transfer_record = db.get(
            Transfer,
            UUID(transfer_id),
        )

        if transfer_record is None:
            raise ValueError(
                "Stored transfer response could not be found."
            )

        return transfer_record

    except Exception:
        db.rollback()
        raise
