import uuid
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.repositories.account import create_account
from app.repositories.user import create_user


client = TestClient(app)


def create_test_user():
    db = SessionLocal()

    user = create_user(
        db=db,
        full_name="Account Test User",
        email=f"{uuid.uuid4()}@example.com",
        phone=f"+234{uuid.uuid4().int % 10_000_000:07d}",
        password_hash=hash_password("TestPassword123"),
    )

    db.close()
    return user


def create_user_with_account(balance=Decimal("1000.00")):
    user = create_test_user()

    db = SessionLocal()

    account_number = (
        f"{uuid.uuid4().int % 10_000_000_00:010d}"
    )

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


def test_create_account_requires_authentication():
    response = client.post(
        "/accounts",
        json={
            "account_number": (
                f"{uuid.uuid4().int % 10_000_000_00:010d}"
            ),
            "currency": "NGN",
        },
    )

    assert response.status_code == 401


def test_authenticated_user_can_create_account():
    user = create_test_user()

    response = client.post(
        "/accounts",
        json={
            "account_number": (
                f"{uuid.uuid4().int % 10_000_000_00:010d}"
            ),
            "currency": "NGN",
        },
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["currency"] == "NGN"
    assert data["balance"] == "0.00"
    assert data["status"] == "active"


def test_user_can_list_own_accounts():
    user = create_test_user()
    headers = create_authenticated_headers(user)

    account_number = (
        f"{uuid.uuid4().int % 10_000_000_00:010d}"
    )

    create_response = client.post(
        "/accounts",
        json={
            "account_number": account_number,
            "currency": "NGN",
        },
        headers=headers,
    )

    assert create_response.status_code == 201

    response = client.get(
        "/accounts",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["account_number"] == account_number


def test_unauthenticated_user_cannot_list_accounts():
    response = client.get("/accounts")

    assert response.status_code == 401


def test_user_can_get_own_account():
    user = create_test_user()
    headers = create_authenticated_headers(user)

    account_number = (
        f"{uuid.uuid4().int % 10_000_000_00:010d}"
    )

    create_response = client.post(
        "/accounts",
        json={
            "account_number": account_number,
            "currency": "NGN",
        },
        headers=headers,
    )

    assert create_response.status_code == 201

    account_id = create_response.json()["id"]

    response = client.get(
        f"/accounts/{account_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == account_id


def test_unauthenticated_user_cannot_view_account():
    user, account = create_user_with_account()

    response = client.get(
        f"/accounts/{account.id}",
    )

    assert response.status_code == 401


def test_user_cannot_access_another_users_account():
    user_one, account = create_user_with_account()
    user_two = create_test_user()

    response = client.get(
        f"/accounts/{account.id}",
        headers=create_authenticated_headers(user_two),
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "You do not have access to this account."
    )


def test_nonexistent_account_returns_404():
    user = create_test_user()

    response = client.get(
        f"/accounts/{uuid.uuid4()}",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 404


def test_duplicate_account_number_is_rejected():
    first_user, first_account = create_user_with_account()
    second_user = create_test_user()

    response = client.post(
        "/accounts",
        json={
            "account_number": first_account.account_number,
            "currency": "NGN",
        },
        headers=create_authenticated_headers(second_user),
    )

    assert response.status_code == 400


def test_user_cannot_create_second_account():
    user, _ = create_user_with_account()

    response = client.post(
        "/accounts",
        json={
            "account_number": (
                f"{uuid.uuid4().int % 10_000_000_00:010d}"
            ),
            "currency": "NGN",
        },
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 400


def test_user_can_view_their_own_account():
    user, account = create_user_with_account(
        Decimal("2500.00")
    )

    response = client.get(
        f"/accounts/{account.id}",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(account.id)
    assert data["account_number"] == account.account_number
    assert data["balance"] == "2500.00"
    assert data["currency"] == "NGN"


def test_account_balance_is_returned_correctly():
    user, account = create_user_with_account(
        Decimal("7500.50")
    )

    response = client.get(
        f"/accounts/{account.id}",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["balance"] == "7500.50"
    assert data["version"] == 0

def test_unauthenticated_user_cannot_view_account_ledger():
    user, account = create_user_with_account()

    response = client.get(
        f"/accounts/{account.id}/ledger",
    )

    assert response.status_code == 401


def test_user_can_view_empty_account_ledger():
    user, account = create_user_with_account()

    response = client.get(
        f"/accounts/{account.id}/ledger",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_user_cannot_view_another_users_account_ledger():
    owner, account = create_user_with_account()
    other_user = create_test_user()

    response = client.get(
        f"/accounts/{account.id}/ledger",
        headers=create_authenticated_headers(other_user),
    )

    assert response.status_code == 403

    assert response.json()["detail"] == (
        "You do not have access to this account."
    )


def test_nonexistent_account_ledger_returns_404():
    user = create_test_user()

    response = client.get(
        f"/accounts/{uuid.uuid4()}/ledger",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 404

def test_account_ledger_returns_transfer_entries():
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    receiver_user, receiver = create_user_with_account(
        Decimal("500.00")
    )

    transfer_response = client.post(
        "/transfers",
        params={
            "idempotency_key": (
                f"ledger-api-{uuid.uuid4()}"
            ),
        },
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert transfer_response.status_code == 201

    response = client.get(
        f"/accounts/{sender.id}/ledger",
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    entry = data[0]

    assert entry["account_id"] == str(sender.id)
    assert entry["transfer_id"] == transfer_response.json()["id"]
    assert entry["direction"] == "debit"
    assert entry["amount"] == "100.00"
    assert entry["balance_after"] == "900.00"

def test_receiver_ledger_returns_credit_entry():
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    receiver_user, receiver = create_user_with_account(
        Decimal("500.00")
    )

    transfer_response = client.post(
        "/transfers",
        params={
            "idempotency_key": f"receiver-ledger-{uuid.uuid4()}",
        },
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert transfer_response.status_code == 201

    response = client.get(
        f"/accounts/{receiver.id}/ledger",
        headers=create_authenticated_headers(receiver_user),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    entry = data[0]

    assert entry["account_id"] == str(receiver.id)
    assert entry["transfer_id"] == transfer_response.json()["id"]
    assert entry["direction"] == "credit"
    assert entry["amount"] == "100.00"
    assert entry["balance_after"] == "600.00"

def test_account_ledger_returns_multiple_entries_newest_first():
    sender_user, sender = create_user_with_account(
        Decimal("1000.00")
    )

    receiver_user, receiver = create_user_with_account(
        Decimal("500.00")
    )

    first_transfer = client.post(
        "/transfers",
        params={
            "idempotency_key": f"ledger-order-1-{uuid.uuid4()}",
        },
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "100.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert first_transfer.status_code == 201

    second_transfer = client.post(
        "/transfers",
        params={
            "idempotency_key": f"ledger-order-2-{uuid.uuid4()}",
        },
        json={
            "receiver_account_number": receiver.account_number,
            "amount": "50.00",
        },
        headers=create_authenticated_headers(sender_user),
    )

    assert second_transfer.status_code == 201

    response = client.get(
        f"/accounts/{sender.id}/ledger",
        headers=create_authenticated_headers(sender_user),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    # Newest ledger entry should come first.
    assert data[0]["transfer_id"] == second_transfer.json()["id"]
    assert data[0]["direction"] == "debit"
    assert data[0]["amount"] == "50.00"
    assert data[0]["balance_after"] == "850.00"

    assert data[1]["transfer_id"] == first_transfer.json()["id"]
    assert data[1]["direction"] == "debit"
    assert data[1]["amount"] == "100.00"
    assert data[1]["balance_after"] == "900.00"