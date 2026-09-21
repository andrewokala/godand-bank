import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import (
    Account,
    AccountStatus,
    LedgerDirection,
    LedgerEntry,
    Transfer,
    User,
)
from app.repositories.account import create_account
from app.repositories.user import create_user


client = TestClient(app)


def make_idempotency_key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


def create_test_user():
    db = SessionLocal()

    user = create_user(
        db=db,
        full_name="Transfer Test User",
        email=f"{uuid.uuid4()}@example.com",
        phone=f"+234{uuid.uuid4().int % 10_000_000:07d}",
        password_hash=hash_password("TestPassword123"),
    )

    db.close()
    return user


def create_user_with_account(balance=Decimal("1000.00")):
    user = create_test_user()

    db = SessionLocal()

    account_number = f"{uuid.uuid4().int % 10_000_000_00:010d}"

    account = create_account(
        db=db,
        user_id=user.id,
        account_number=account_number,
        currency="NGN",
    )

    account.balance = balance

    db.commit()
    db.refresh(account)
    db.close()

    return user, account


def create_authenticated_headers(user):
    token = create_access_token(user.id)

    return {
        "Authorization": f"Bearer {token}",
    }


def test_transfer_requires_authentication():
    _, receiver = create_user_with_account()

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('unauthenticated')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
    )

    assert response.status_code == 401


def test_successful_transfer_updates_balances():
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('successful')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 201

    db = SessionLocal()

    sender_after = db.get(Account, sender.id)
    receiver_after = db.get(Account, receiver.id)

    assert sender_after.balance == Decimal("900.00")
    assert receiver_after.balance == Decimal("600.00")

    assert sender_after.version == 1
    assert receiver_after.version == 1

    db.close()


def test_successful_transfer_creates_two_ledger_entries():
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('ledger')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 201

    transfer_id = response.json()["id"]

    db = SessionLocal()

    entries = list(
        db.scalars(
            select(LedgerEntry).where(
                LedgerEntry.transfer_id == uuid.UUID(transfer_id)
            )
        ).all()
    )

    assert len(entries) == 2

    directions = {entry.direction for entry in entries}

    assert LedgerDirection.DEBIT in directions
    assert LedgerDirection.CREDIT in directions

    debit_entry = next(
        entry
        for entry in entries
        if entry.direction == LedgerDirection.DEBIT
    )

    credit_entry = next(
        entry
        for entry in entries
        if entry.direction == LedgerDirection.CREDIT
    )

    assert debit_entry.account_id == sender.id
    assert debit_entry.amount == Decimal("100.00")
    assert debit_entry.balance_after == Decimal("900.00")

    assert credit_entry.account_id == receiver.id
    assert credit_entry.amount == Decimal("100.00")
    assert credit_entry.balance_after == Decimal("600.00")

    db.close()


def test_invalid_receiver_returns_404():
    sender_user, _ = create_user_with_account()

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('invalid-receiver')}",
        json={
            "receiver_account_number": "9999999999",
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 404


def test_insufficient_balance():
    sender_user, _ = create_user_with_account(
        Decimal("50.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('insufficient')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient balance."


def test_self_transfer_is_rejected():
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('self-transfer')}",
        json={
            "receiver_account_number": sender.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Sender and receiver accounts must be different."
    )


def test_inactive_sender_is_rejected():
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    db = SessionLocal()

    sender = db.get(Account, sender.id)
    sender.status = AccountStatus.FROZEN

    db.commit()
    db.refresh(sender)

    assert sender.status == AccountStatus.FROZEN

    db.close()

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('inactive')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Sender account is not active."

def test_duplicate_idempotency_key_returns_same_transfer():
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    idempotency_key = make_idempotency_key("duplicate")

    payload = {
        "receiver_account_number": receiver.account_number,
        "amount": "100.00",
    }

    headers = create_authenticated_headers(sender_user)

    first_response = client.post(
        f"/transfers?idempotency_key={idempotency_key}",
        json=payload,
        headers=headers,
    )

    second_response = client.post(
        f"/transfers?idempotency_key={idempotency_key}",
        json=payload,
        headers=headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_data = first_response.json()
    second_data = second_response.json()

    assert first_data["id"] == second_data["id"]
    assert first_data["reference"] == second_data["reference"]

    db = SessionLocal()

    sender_after = db.get(Account, sender.id)
    receiver_after = db.get(Account, receiver.id)

    assert sender_after.balance == Decimal("900.00")
    assert receiver_after.balance == Decimal("600.00")

    transfers = list(
        db.scalars(
            select(Transfer).where(
                Transfer.id == uuid.UUID(first_data["id"])
            )
        ).all()
    )

    assert len(transfers) == 1

    db.close()


def test_idempotency_key_with_different_request_is_rejected():
    sender_user, _ = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    idempotency_key = make_idempotency_key("conflict")

    first_response = client.post(
        f"/transfers?idempotency_key={idempotency_key}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    second_response = client.post(
        f"/transfers?idempotency_key={idempotency_key}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "200.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400

    assert second_response.json()["detail"] == (
        "Idempotency key was already used with a different request."
    )


def test_transfer_always_uses_authenticated_users_account_as_sender():
    victim_user, victim = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    attacker_user, attacker = create_user_with_account(
        Decimal("1000.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('authenticated-sender')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(attacker_user),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["sender_account_id"] == str(attacker.id)
    assert data["receiver_account_id"] == str(receiver.id)

    db = SessionLocal()

    victim_after = db.get(Account, victim.id)
    attacker_after = db.get(Account, attacker.id)
    receiver_after = db.get(Account, receiver.id)

    assert victim_after.balance == Decimal("1000.00")
    assert attacker_after.balance == Decimal("900.00")
    assert receiver_after.balance == Decimal("600.00")

    db.close()

def test_authenticated_user_can_list_their_transfers():
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('history-list')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 201

    transfer_id = response.json()["id"]

    response = client.get(
        "/transfers",
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) >= 1

    transfer_ids = [item["id"] for item in data]

    assert transfer_id in transfer_ids


def test_unauthenticated_user_cannot_list_transfers():
    response = client.get("/transfers")

    assert response.status_code == 401


def test_sender_can_get_their_transfer():
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('history-detail')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 201

    transfer_id = response.json()["id"]

    response = client.get(
        f"/transfers/{transfer_id}",
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == transfer_id
    assert data["amount"] == "100.00"


def test_receiver_can_get_the_transfer():
    sender_user, _ = create_user_with_account(
        Decimal("1000.00")
    )

    receiver_user, receiver = create_user_with_account(
        Decimal("500.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('receiver-history')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 201

    transfer_id = response.json()["id"]

    response = client.get(
        f"/transfers/{transfer_id}",
        headers=create_authenticated_headers(receiver_user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == transfer_id
    assert data["receiver_account_id"] == str(receiver.id)


def test_unrelated_user_cannot_get_transfer():
    sender_user, _ = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    unrelated_user, _ = create_user_with_account(
        Decimal("1000.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('private-history')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 201

    transfer_id = response.json()["id"]

    response = client.get(
        f"/transfers/{transfer_id}",
        headers=create_authenticated_headers(unrelated_user),
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "You do not have access to this transfer."
    )


def test_nonexistent_transfer_returns_404():
    user, _ = create_user_with_account()

    fake_transfer_id = str(uuid.uuid4())

    response = client.get(
        f"/transfers/{fake_transfer_id}",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 404

    assert response.json()["detail"] == "Transfer not found."


def test_transfer_history_is_newest_first():
    sender_user, _ = create_user_with_account(
        Decimal("2000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    first_response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('history-order-1')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert first_response.status_code == 201

    second_response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('history-order-2')}",
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "200.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert second_response.status_code == 201

    first_id = first_response.json()["id"]
    second_id = second_response.json()["id"]

    response = client.get(
        "/transfers",
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 200

    data = response.json()

    transfer_ids = [item["id"] for item in data]

    first_position = transfer_ids.index(first_id)
    second_position = transfer_ids.index(second_id)

    assert second_position < first_position