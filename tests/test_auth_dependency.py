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
from app.models import KYCStatus, RevokedToken, User


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
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=30),
                "jti": str(uuid4()),
                "type": "access",
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

def test_locked_user_cannot_access_protected_route():
    db = SessionLocal()

    try:
        user = User(
            id=uuid4(),
            full_name="Locked User",
            email=f"locked-{uuid4()}@example.com",
            phone=f"+234{uuid4().int % 10_000_000:07d}",
            password_hash="not-used",
            terms_accepted_at=datetime.now(UTC),
            failed_login_count=5,
            locked_until=datetime.now(UTC) + timedelta(minutes=15),
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

        assert response.status_code == 403
        assert response.json()["detail"] == "Account is temporarily locked."

    finally:
        db.close()


def test_rejected_kyc_user_cannot_access_protected_route():
    db = SessionLocal()

    try:
        user = User(
            id=uuid4(),
            full_name="Rejected KYC User",
            email=f"rejected-kyc-{uuid4()}@example.com",
            phone=f"+234{uuid4().int % 10_000_000:07d}",
            password_hash="not-used",
            terms_accepted_at=datetime.now(UTC),
            kyc_status=KYCStatus.REJECTED,
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

        assert response.status_code == 403
        assert response.json()["detail"] == "Account KYC has been rejected."

    finally:
        db.close()

def test_wrong_token_type_is_rejected():
    db = SessionLocal()

    try:
        user = User(
            id=uuid4(),
            full_name="Wrong Token Type User",
            email=f"wrong-type-{uuid4()}@example.com",
            phone=f"+234{uuid4().int % 10_000_000:07d}",
            password_hash="not-used",
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        token = jwt.encode(
            {
                "sub": str(user.id),
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=30),
                "jti": str(uuid4()),
                "type": "refresh",
            },
            settings.secret_key,
            algorithm=settings.algorithm,
        )

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
        assert response.json()["detail"] == "Invalid token type."

    finally:
        db.close()


def test_token_signed_with_wrong_secret_is_rejected():
    db = SessionLocal()

    try:
        user = User(
            id=uuid4(),
            full_name="Wrong Secret User",
            email=f"wrong-secret-{uuid4()}@example.com",
            phone=f"+234{uuid4().int % 10_000_000:07d}",
            password_hash="not-used",
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        token = jwt.encode(
            {
                "sub": str(user.id),
                "exp": datetime.now(UTC) + timedelta(minutes=30),
                "type": "access",
            },
            "wrong-secret",
            algorithm=settings.algorithm,
        )

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
        assert response.json()["detail"] == "Invalid or expired token."

    finally:
        db.close()


def test_token_without_jti_is_rejected():
    db = SessionLocal()

    try:
        user = User(
            id=uuid4(),
            full_name="Missing JTI User",
            email=f"missing-jti-{uuid4()}@example.com",
            phone=f"+234{uuid4().int % 10_000_000:07d}",
            password_hash="not-used",
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        token = jwt.encode(
            {
                "sub": str(user.id),
                "exp": datetime.now(UTC) + timedelta(minutes=30),
                "type": "access",
            },
            settings.secret_key,
            algorithm=settings.algorithm,
        )

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
        assert response.json()["detail"] == "Invalid token ID."

    finally:
        db.close()

def test_token_without_iat_is_rejected():
    db = SessionLocal()

    try:
        user = User(
            id=uuid4(),
            full_name="Missing IAT User",
            email=f"missing-iat-{uuid4()}@example.com",
            phone=f"+234{uuid4().int % 10_000_000:07d}",
            password_hash="not-used",
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        token = jwt.encode(
            {
                "sub": str(user.id),
                "exp": datetime.now(UTC) + timedelta(minutes=30),
                "jti": str(uuid4()),
                "type": "access",
            },
            settings.secret_key,
            algorithm=settings.algorithm,
        )

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
        assert response.json()["detail"] == "Invalid token issue time."

    finally:
        db.close()

def test_revoked_token_is_rejected():
    db = SessionLocal()

    try:
        user = User(
            id=uuid4(),
            full_name="Revoked Token User",
            email=f"revoked-{uuid4()}@example.com",
            phone=f"+234{uuid4().int % 10_000_000:07d}",
            password_hash="not-used",
            terms_accepted_at=datetime.now(UTC),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(user_id=user.id)

        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )

        from app.repositories.revoked_token import revoke_token

        revoke_token(
            db=db,
            jti=payload["jti"],
            user_id=user.id,
            expires_at=datetime.fromtimestamp(
                payload["exp"],
                tz=UTC,
            ),
        )

        db.commit()

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
        assert response.json()["detail"] == "Token has been revoked."

    finally:
        if "user" in locals():
            db.query(RevokedToken).filter(
                RevokedToken.user_id == user.id
            ).delete()
            db.delete(user)
            db.commit()
        else:
            db.rollback()

        db.close()
