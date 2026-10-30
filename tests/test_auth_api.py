import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models import RevokedToken, User
from app.models.auth_session import AuthSession
from app.models.refresh_token import RefreshToken
from app.repositories.user import create_user
from app.services.auth_session import create_auth_session
from app.services.refresh_token import create_refresh_token

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

        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id
        ).delete(synchronize_session=False)

        db.query(AuthSession).filter(
            AuthSession.user_id == user_id
        ).delete(synchronize_session=False)

        db.query(User).filter(
            User.id == user_id
        ).delete(synchronize_session=False)

        db.commit()

    finally:
        db.close()

def create_session_tokens(user_id):
    db = SessionLocal()

    try:
        auth_session = create_auth_session(
            db=db,
            user_id=user_id,
        )

        access_token_1 = create_access_token(
            user_id=user_id,
            session_id=auth_session.id,
        )

        access_token_2 = create_access_token(
            user_id=user_id,
            session_id=auth_session.id,
        )

        refresh_token_1 = create_refresh_token(
            db=db,
            user_id=user_id,
            session_id=auth_session.id,
        )

        refresh_token_2 = create_refresh_token(
            db=db,
            user_id=user_id,
            session_id=auth_session.id,
        )

        session_id = auth_session.id

        db.commit()

        return {
            "session_id": session_id,
            "access_token_1": access_token_1,
            "access_token_2": access_token_2,
            "refresh_token_1": refresh_token_1,
            "refresh_token_2": refresh_token_2,
        }

    except Exception:
        db.rollback()
        raise

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

def test_logout_revokes_entire_authentication_session():
    user = create_test_user()

    try:
        tokens = create_session_tokens(user.id)

        logout_response = client.post(
            "/auth/logout",
            headers={
                "Authorization": (
                    f"Bearer {tokens['access_token_1']}"
                ),
            },
        )

        assert logout_response.status_code == 200

        db = SessionLocal()

        try:
            auth_session = db.get(
                AuthSession,
                tokens["session_id"],
            )

            assert auth_session is not None
            assert auth_session.revoked_at is not None

            refresh_tokens = (
                db.query(RefreshToken)
                .filter(
                    RefreshToken.session_id == tokens["session_id"]
                )
                .all()
            )

            assert len(refresh_tokens) == 2

            assert all(
                token.revoked_at is not None
                for token in refresh_tokens
            )

        finally:
            db.close()

        protected_response = client.get(
            "/accounts",
            headers={
                "Authorization": (
                    f"Bearer {tokens['access_token_2']}"
                ),
            },
        )

        assert protected_response.status_code == 401

        for refresh_token in (
            tokens["refresh_token_1"],
            tokens["refresh_token_2"],
        ):
            refresh_response = client.post(
                "/auth/refresh",
                json={"refresh_token": refresh_token},
            )

            assert refresh_response.status_code == 401

    finally:
        cleanup_test_user(user.id)

def test_user_cannot_revoke_another_users_session():
    user_a = create_test_user()
    user_b = create_test_user()

    try:
        user_a_tokens = create_session_tokens(user_a.id)
        user_b_tokens = create_session_tokens(user_b.id)

        response = client.post(
            "/auth/logout",
            headers={
                "Authorization": (
                    f"Bearer {user_a_tokens['access_token_1']}"
                ),
            },
        )

        assert response.status_code == 200

        # User B's session must remain active.
        db = SessionLocal()

        try:
            user_b_session = db.get(
                AuthSession,
                user_b_tokens["session_id"],
            )

            assert user_b_session is not None
            assert user_b_session.revoked_at is None

        finally:
            db.close()

        # User B must still be able to use their refresh token.
        refresh_response = client.post(
            "/auth/refresh",
            json={
                "refresh_token": user_b_tokens["refresh_token_1"],
            },
        )

        assert refresh_response.status_code == 200

    finally:
        cleanup_test_user(user_a.id)
        cleanup_test_user(user_b.id)