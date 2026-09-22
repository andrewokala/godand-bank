import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.repositories.audit_log import create_audit_log
from app.repositories.user import create_user


client = TestClient(app)


def create_test_user():
    db = SessionLocal()

    user = create_user(
        db=db,
        full_name="Audit API Test User",
        email=f"{uuid.uuid4()}@example.com",
        phone=f"+234{uuid.uuid4().int % 10_000_000:07d}",
        password_hash=hash_password("TestPassword123"),
    )

    db.close()
    return user


def create_authenticated_headers(user):
    token = create_access_token(user.id)

    return {
        "Authorization": f"Bearer {token}",
    }


def test_audit_logs_requires_authentication():
    response = client.get("/audit-logs")

    assert response.status_code == 401


def test_authenticated_user_with_no_audit_logs_gets_empty_list():
    user = create_test_user()

    response = client.get(
        "/audit-logs",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 200
    data = response.json()

    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0

def test_user_can_view_own_audit_logs():
    user = create_test_user()

    db = SessionLocal()

    create_audit_log(
        db=db,
        actor_user_id=user.id,
        action="profile.updated",
        ip_address="127.0.0.1",
        metadata_json={
            "source": "test",
            "description": "Profile updated",
        },
    )

    db.commit()
    db.close()

    response = client.get(
        "/audit-logs",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert data["limit"] == 20
    assert data["offset"] == 0

    assert len(data["items"]) == 1
    assert data["items"][0]["actor_user_id"] == str(user.id)
    assert data["items"][0]["action"] == "profile.updated"
    assert data["items"][0]["ip_address"] == "127.0.0.1"
    assert data["items"][0]["metadata_json"]["source"] == "test"

def test_user_cannot_view_another_users_audit_logs():
    user_a = create_test_user()
    user_b = create_test_user()

    db = SessionLocal()

    create_audit_log(
        db=db,
        actor_user_id=user_b.id,
        action="sensitive.action",
        ip_address="192.168.1.50",
        metadata_json={
            "secret": "user-b-data",
        },
    )

    db.commit()
    db.close()

    response = client.get(
        "/audit-logs",
        headers=create_authenticated_headers(user_a),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["items"] == []
    assert data["total"] == 0

def test_audit_logs_pagination():
    user = create_test_user()

    db = SessionLocal()

    for index in range(5):
        create_audit_log(
            db=db,
            actor_user_id=user.id,
            action=f"test.action.{index}",
            ip_address="127.0.0.1",
            metadata_json={
                "index": index,
            },
        )

    db.commit()
    db.close()

    response = client.get(
        "/audit-logs?limit=2&offset=0",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert len(data["items"]) == 2


def test_audit_logs_pagination_offset():
    user = create_test_user()

    db = SessionLocal()

    for index in range(5):
        create_audit_log(
            db=db,
            actor_user_id=user.id,
            action=f"test.action.{index}",
            ip_address="127.0.0.1",
            metadata_json={
                "index": index,
            },
        )

    db.commit()
    db.close()

    response = client.get(
        "/audit-logs?limit=2&offset=2",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 2
    assert len(data["items"]) == 2


def test_audit_logs_limit_cannot_exceed_100():
    user = create_test_user()

    response = client.get(
        "/audit-logs?limit=101",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 422


def test_audit_logs_limit_must_be_positive():
    user = create_test_user()

    response = client.get(
        "/audit-logs?limit=0",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 422


def test_audit_logs_offset_cannot_be_negative():
    user = create_test_user()

    response = client.get(
        "/audit-logs?offset=-1",
        headers=create_authenticated_headers(user),
    )

    assert response.status_code == 422