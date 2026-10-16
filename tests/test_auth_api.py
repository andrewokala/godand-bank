import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models import RevokedToken, User
from app.repositories.user import create_user


client = TestClient(app)


def create_test_user():
    db = SessionLocal()

    user = create_user(
        db=db,
        full_name="Logout Test User",
        email=f"logout-{uuid.uuid4()}@example.com",
        phone=f"+23480{uuid.uuid4().int % 10_000_000:07d}",
        password_hash="hashed-password",
    )

    db.close()

    return user


def cleanup_test_user(user_id):
    db = SessionLocal()

    try:
        db.query(RevokedToken).filter(
            RevokedToken.user_id == user_id
        ).delete(synchronize_session=False)

        db.query(User).filter(
            User.id == user_id
        ).delete(synchronize_session=False)

        db.commit()

    finally:
        db.close()


def test_logout_revokes_token():
    user = create_test_user()

    try:
        token = create_access_token(user.id)

        response = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully."

        protected_response = client.get(
            "/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert protected_response.status_code == 401

    finally:
        cleanup_test_user(user.id)


def test_logout_rejects_already_revoked_token():
    user = create_test_user()

    try:
        token = create_access_token(user.id)

        headers = {
            "Authorization": f"Bearer {token}",
        }

        first_response = client.post(
            "/auth/logout",
            headers=headers,
        )

        assert first_response.status_code == 200

        second_response = client.post(
            "/auth/logout",
            headers=headers,
        )

        assert second_response.status_code == 401
        assert second_response.json()["detail"] == "Token has been revoked."

    finally:
        cleanup_test_user(user.id)
