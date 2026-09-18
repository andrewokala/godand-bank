from app.models import Transfer


def build_transfer_response_snapshot(
    transfer: Transfer,
) -> dict:
    return {
        "id": str(transfer.id),
        "reference": transfer.reference,
        "sender_account_id": str(transfer.sender_account_id),
        "receiver_account_id": str(transfer.receiver_account_id),
        "amount": str(transfer.amount),
        "currency": transfer.currency,
        "note": transfer.note,
        "status": transfer.status.value,
        "created_at": transfer.created_at.isoformat(),
    }
