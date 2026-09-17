from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Transaction, Transfer
from app.repositories.account import get_account_by_number


def transfer(
    db: Session,
    sender_account_number: str,
    receiver_account_number: str,
    amount: Decimal,
) -> Transfer:
    if amount <= 0:
        raise ValueError("Transfer amount must be greater than zero.")

    if sender_account_number == receiver_account_number:
        raise ValueError("Sender and receiver accounts must be different.")

    sender = get_account_by_number(
        db=db,
        account_number=sender_account_number,
    )

    if sender is None:
        raise ValueError("Sender account not found.")

    receiver = get_account_by_number(
        db=db,
        account_number=receiver_account_number,
    )

    if receiver is None:
        raise ValueError("Receiver account not found.")

    if sender.status != "active":
        raise ValueError("Sender account is not active.")

    if receiver.status != "active":
        raise ValueError("Receiver account is not active.")

    if sender.balance < amount:
        raise ValueError("Insufficient balance.")

    reference = f"TRF-{uuid4().hex[:12].upper()}"

    sender.balance -= amount
    receiver.balance += amount

    transfer_record = Transfer(
        sender_account_id=sender.id,
        receiver_account_id=receiver.id,
        amount=amount,
        reference=reference,
        status="completed",
    )

    sender_transaction = Transaction(
        account_id=sender.id,
        transaction_type="transfer_out",
        amount=amount,
        reference=f"{reference}-OUT",
        description=f"Transfer to account {receiver.account_number}",
    )

    receiver_transaction = Transaction(
        account_id=receiver.id,
        transaction_type="transfer_in",
        amount=amount,
        reference=f"{reference}-IN",
        description=f"Transfer from account {sender.account_number}",
    )

    db.add(transfer_record)
    db.add(sender_transaction)
    db.add(receiver_transaction)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(transfer_record)

    return transfer_record