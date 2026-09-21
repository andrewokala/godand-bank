import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models import User
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


def test_create_account_requires_authentication():
    response = client.post(
        "/accounts",
        json={
            "account_number": f"{uuid.uuid4().int % 10_000_000_00:010d}",
            "currency": "NGN",
        },
    )

    assert response.status_code == 401


def test_authenticated_user_can_create_account():
    user = create_test_user()
    token = create_access_token(user.id)

    account_number = f"{uuid.uuid4().int % 10_000_000_00:010d}"

    response = client.post(
        "/accounts",
        json={
            "account_number": account_number,
            "currency": "NGN",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["account_number"] == account_number
    assert data["currency"] == "NGN"
    assert data["balance"] == "0.00"
    assert data["status"] == "active"


def test_user_can_list_own_accounts():
    user = create_test_user()
    token = create_access_token(user.id)

    account_number = f"{uuid.uuid4().int % 10_000_000_00:010d}"

    create_response = client.post(
        "/accounts",
        json={
            "account_number": account_number,
            "currency": "NGN",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert create_response.status_code == 201

    response = client.get(
        "/accounts",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["account_number"] == account_number


def test_user_can_get_own_account():
    user = create_test_user()
    token = create_access_token(user.id)

    account_number = f"{uuid.uuid4().int % 10_000_000_00:010d}"

    create_response = client.post(
        "/accounts",
        json={
            "account_number": account_number,
            "currency": "NGN",
        },
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert create_response.status_code == 201

    account_id = create_response.json()["id"]

    response = client.get(
        f"/accounts/{account_id}",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == account_id


def test_user_cannot_access_another_users_account():
    user_one = create_test_user()
    user_two = create_test_user()

    token_one = create_access_token(user_one.id)
    token_two = create_access_token(user_two.id)

    account_number = f"{uuid.uuid4().int % 10_000_000_00:010d}"

    create_response = client.post(
        "/accounts",
        json={
            "account_number": account_number,
            "currency": "NGN",
        },
        headers={
            "Authorization": f"Bearer {token_one}",
        },
    )

    assert create_response.status_code == 201

    account_id = create_response.json()["id"]

    response = client.get(
        f"/accounts/{account_id}",
        headers={
            "Authorization": f"Bearer {token_two}",
        },
    )

    assert response.status_code == 403


def test_nonexistent_account_returns_404():
    user = create_test_user()
    token = create_access_token(user.id)

    response = client.get(
        f"/accounts/{uuid.uuid4()}",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 404


def test_duplicate_account_number_is_rejected():
    user_one = create_test_user()
    user_two = create_test_user()

    token_one = create_access_token(user_one.id)
    token_two = create_access_token(user_two.id)

    account_number = f"{uuid.uuid4().int % 10_000_000_00:010d}"

    first_response = client.post(
        "/accounts",
        json={
            "account_number": account_number,
            "currency": "NGN",
        },
        headers={
            "Authorization": f"Bearer {token_one}",
        },
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/accounts",
        json={
            "account_number": account_number,
            "currency": "NGN",
        },
        headers={
            "Authorization": f"Bearer {token_two}",
        },
    )

    assert second_response.status_code == 400
