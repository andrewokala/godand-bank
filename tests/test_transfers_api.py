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
            "sender_account_number": sender.account_number,
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
            "sender_account_number": sender.account_number,
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
    sender_user, sender = create_user_with_account()

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('invalid-receiver')}",
        json={
            "sender_account_number": sender.account_number,
            "receiver_account_number": "9999999999",
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 404


def test_insufficient_balance():
    sender_user, sender = create_user_with_account(
        Decimal("50.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('insufficient')}",
        json={
            "sender_account_number": sender.account_number,
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
            "sender_account_number": sender.account_number,
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
            "sender_account_number": sender.account_number,
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
        "sender_account_number": sender.account_number,
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
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    idempotency_key = make_idempotency_key("conflict")

    first_response = client.post(
        f"/transfers?idempotency_key={idempotency_key}",
        json={
            "sender_account_number": sender.account_number,
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    second_response = client.post(
        f"/transfers?idempotency_key={idempotency_key}",
        json={
            "sender_account_number": sender.account_number,
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


def test_user_cannot_transfer_from_another_users_account():
    _, victim = create_user_with_account(
        Decimal("1000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    attacker_user, attacker = create_user_with_account(
        Decimal("1000.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('unauthorized-sender')}",
        json={
            "sender_account_number": victim.account_number,
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(attacker_user),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You do not have access to this sender account."
    )

    db = SessionLocal()

    victim_after = db.get(Account, victim.id)
    attacker_after = db.get(Account, attacker.id)
    receiver_after = db.get(Account, receiver.id)

    assert victim_after.balance == Decimal("1000.00")
    assert attacker_after.balance == Decimal("1000.00")
    assert receiver_after.balance == Decimal("500.00")

    transfer = db.scalar(
        select(Transfer).where(
            Transfer.sender_account_id == victim.id
        )
    )

    assert transfer is None

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
            "sender_account_number": sender.account_number,
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

    assert len(data["items"]) >= 1

    transfer_ids = [
        item["id"]
        for item in data["items"]
    ]

    assert transfer_id in transfer_ids


def test_user_cannot_see_another_users_transfers_in_history():
    first_user, first_sender = create_user_with_account(
        Decimal("1000.00")
    )

    _, first_receiver = create_user_with_account(
        Decimal("500.00")
    )

    second_user, second_sender = create_user_with_account(
        Decimal("1000.00")
    )

    _, second_receiver = create_user_with_account(
        Decimal("500.00")
    )

    first_response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('history-isolation-first')}",
        json={
            "sender_account_number": first_sender.account_number,
            "receiver_account_number": first_receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(first_user),
    )

    assert first_response.status_code == 201

    second_response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('history-isolation-second')}",
        json={
            "sender_account_number": second_sender.account_number,
            "receiver_account_number": second_receiver.account_number,
            "amount": "200.00",
        },
        headers=create_authenticated_headers(second_user),
    )

    assert second_response.status_code == 201

    first_transfer_id = first_response.json()["id"]
    second_transfer_id = second_response.json()["id"]

    response = client.get(
        "/transfers",
        headers=create_authenticated_headers(first_user),
    )

    assert response.status_code == 200

    data = response.json()

    transfer_ids = {
        item["id"]
        for item in data["items"]
    }

    assert first_transfer_id in transfer_ids
    assert second_transfer_id not in transfer_ids


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
            "sender_account_number": sender.account_number,
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
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    receiver_user, receiver = create_user_with_account(
        Decimal("500.00")
    )

    response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('receiver-history')}",
        json={
            "sender_account_number": sender.account_number,
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
    sender_user, sender = create_user_with_account(
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
            "sender_account_number": sender.account_number,
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
    sender_user, sender = create_user_with_account(
        Decimal("2000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("500.00")
    )

    first_response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('history-order-1')}",
        json={
            "sender_account_number": sender.account_number,
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert first_response.status_code == 201

    second_response = client.post(
        f"/transfers?idempotency_key={make_idempotency_key('history-order-2')}",
        json={
            "sender_account_number": sender.account_number,
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

    transfer_ids = [
        item["id"]
        for item in data["items"]
        ]

    first_position = transfer_ids.index(first_id)
    second_position = transfer_ids.index(second_id)

    assert second_position < first_position

def test_get_my_transfers_returns_paginated_history():
    sender_user, sender = create_user_with_account(
        Decimal("5000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("1000.00")
    )

    headers = create_authenticated_headers(sender_user)

    for index in range(3):
        response = client.post(
            f"/transfers?idempotency_key={make_idempotency_key(f'pagination-{index}')}",
            json={
                "sender_account_number": sender.account_number,
                "receiver_account_number": receiver.account_number,
                "amount": "100.00",
            },
            headers=headers,
        )

        assert response.status_code == 201

    response = client.get(
        "/transfers?limit=2&offset=0",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["items"]) == 2
    assert data["total"] == 3
    assert data["limit"] == 2
    assert data["offset"] == 0


def test_get_my_transfers_returns_next_page():
    sender_user, sender = create_user_with_account(
        Decimal("5000.00")
    )

    _, receiver = create_user_with_account(
        Decimal("1000.00")
    )

    headers = create_authenticated_headers(sender_user)

    created_transfer_ids = []

    for index in range(3):
        response = client.post(
            f"/transfers?idempotency_key={make_idempotency_key(f'pagination-next-{index}')}",
            json={
                "sender_account_number": sender.account_number,
                "receiver_account_number": receiver.account_number,
                "amount": "100.00",
            },
            headers=headers,
        )

        assert response.status_code == 201
        created_transfer_ids.append(response.json()["id"])

    first_page = client.get(
        "/transfers?limit=2&offset=0",
        headers=headers,
    )

    second_page = client.get(
        "/transfers?limit=2&offset=2",
        headers=headers,
    )

    assert first_page.status_code == 200
    assert second_page.status_code == 200

    first_data = first_page.json()
    second_data = second_page.json()

    assert len(first_data["items"]) == 2
    assert len(second_data["items"]) == 1

    first_ids = {
        item["id"]
        for item in first_data["items"]
    }

    second_ids = {
        item["id"]
        for item in second_data["items"]
    }

    assert first_ids.isdisjoint(second_ids)

    returned_ids = first_ids | second_ids

    assert returned_ids == set(created_transfer_ids)

    assert second_data["total"] == 3
    assert second_data["limit"] == 2
    assert second_data["offset"] == 2


def test_get_my_transfers_rejects_invalid_pagination():
    user, _ = create_user_with_account()

    headers = create_authenticated_headers(user)

    negative_limit = client.get(
        "/transfers?limit=0",
        headers=headers,
    )

    oversized_limit = client.get(
        "/transfers?limit=101",
        headers=headers,
    )

    negative_offset = client.get(
        "/transfers?offset=-1",
        headers=headers,
    )

    assert negative_limit.status_code == 422
    assert oversized_limit.status_code == 422
    assert negative_offset.status_code == 422