from datetime import UTC, datetime
import uuid

from sqlalchemy.orm import Session

from app.models import RevokedToken


def get_revoked_token(
    db: Session,
    jti: str,
) -> RevokedToken | None:
    return db.get(RevokedToken, jti)


def revoke_token(
    db: Session,
    jti: str,
    user_id: uuid.UUID,
    expires_at: datetime,
) -> RevokedToken:
    record = RevokedToken(
        jti=jti,
        user_id=user_id,
        revoked_at=datetime.now(UTC),
        expires_at=expires_at,
    )

    db.add(record)
    db.flush()

    return record
