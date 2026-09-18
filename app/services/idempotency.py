import hashlib
import json
import uuid
from decimal import Decimal


def build_transfer_request_hash(
    user_id: uuid.UUID,
    sender_account_number: str,
    receiver_account_number: str,
    amount: Decimal,
    currency: str,
    note: str | None,
) -> str:
    payload = {
        "user_id": str(user_id),
        "sender_account_number": sender_account_number,
        "receiver_account_number": receiver_account_number,
        "amount": str(amount),
        "currency": currency,
        "note": note,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()
