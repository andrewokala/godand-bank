from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db.session import SessionLocal
from app.models import KYCStatus, RevokedToken, User
from app.repositories.revoked_token import (
    get_revoked_token,
    revoke_token,
)


def create_test_user(db):
    user = User(
        full_name="Revoked Token Test User",
        email=f"revoked-{uuid4().hex}@test.godandbank.local",
        phone=f"+23480{uuid4().int % 10_000_000:07d}",
        password_hash="test_hash",
        kyc_status=KYCStatus.VERIFIED,
        terms_accepted_at=datetime.now(UTC),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def test_revoke_token_creates_revocation_record():
    db = SessionLocal()
    user = None

    try:
        user = create_test_user(db)

        jti = str(uuid4())
        expires_at = datetime.now(UTC) + timedelta(minutes=30)

        record = revoke_token(
            db=db,
            jti=jti,
            user_id=user.id,
            expires_at=expires_at,
        )

        db.commit()
        db.refresh(record)

        assert record.jti == jti
        assert record.user_id == user.id
        assert record.expires_at == expires_at
        assert record.revoked_at is not None

    finally:
        db.rollback()

        if user is not None:
            db.query(RevokedToken).filter(
                RevokedToken.user_id == user.id
            ).delete(synchronize_session=False)

            db.query(User).filter(
                User.id == user.id
            ).delete(synchronize_session=False)

        db.commit()
        db.close()


def test_get_revoked_token_returns_record_by_jti():
    db = SessionLocal()
    user = None

    try:
        user = create_test_user(db)

        jti = str(uuid4())
        expires_at = datetime.now(UTC) + timedelta(minutes=30)

        revoke_token(
            db=db,
            jti=jti,
            user_id=user.id,
            expires_at=expires_at,
        )

        db.commit()

        record = get_revoked_token(
            db=db,
            jti=jti,
        )

        assert record is not None
        assert record.jti == jti
        assert record.user_id == user.id

    finally:
        db.rollback()

        if user is not None:
            db.query(RevokedToken).filter(
                RevokedToken.user_id == user.id
            ).delete(synchronize_session=False)

            db.query(User).filter(
                User.id == user.id
            ).delete(synchronize_session=False)

        db.commit()
        db.close()
