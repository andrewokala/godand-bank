from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.security import create_access_token
from app.db.dependencies import get_db
from app.db.session import SessionLocal
from app.models import User


def create_test_app():
    app = FastAPI()

    @app.get("/protected")
    def protected_route(user: User = Depends(get_current_user)):
        return {
            "user_id": str(user.id),
            "email": user.email,
        }

    return app


def test_valid_token_allows_access():
    db = SessionLocal()

    try:
        user = User(
            id=uuid4(),
            full_name="Test User",
            email=f"auth-{uuid4()}@example.com",
            phone=f"+234{uuid4().int % 10_000_000:07d}",
            password_hash="not-used",
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(user_id=user.id)

        app = create_test_app()

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["user_id"] == str(user.id)
        assert response.json()["email"] == user.email

    finally:
        db.close()


def test_missing_token_is_rejected():
    db = SessionLocal()

    try:
        app = create_test_app()

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        response = client.get("/protected")

        assert response.status_code == 401

    finally:
        db.close()


def test_invalid_token_is_rejected():
    db = SessionLocal()

    try:
        app = create_test_app()

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        response = client.get(
            "/protected",
            headers={"Authorization": "Bearer this-is-not-a-real-token"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token."

    finally:
        db.close()


def test_expired_token_is_rejected():
    db = SessionLocal()

    try:
        app = create_test_app()

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        expired_token = jwt.encode(
            {
                "sub": str(uuid4()),
                "exp": datetime.now(UTC) - timedelta(minutes=1),
            },
            settings.secret_key,
            algorithm=settings.algorithm,
        )

        client = TestClient(app)

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {expired_token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token."

    finally:
        db.close()


def test_token_with_invalid_subject_is_rejected():
    db = SessionLocal()

    try:
        app = create_test_app()

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        token = jwt.encode(
            {
                "sub": "not-a-uuid",
                "exp": datetime.now(UTC) + timedelta(minutes=30),
            },
            settings.secret_key,
            algorithm=settings.algorithm,
        )

        client = TestClient(app)

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token subject."

    finally:
        db.close()


def test_token_for_nonexistent_user_is_rejected():
    db = SessionLocal()

    try:
        token = create_access_token(user_id=uuid4())

        app = create_test_app()

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        client = TestClient(app)

        response = client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "User not found."

    finally:
        db.close()
