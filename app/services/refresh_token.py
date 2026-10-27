import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.models.refresh_token import RefreshToken
from app.models import KYCStatus
from app.models.user import User
from app.services.auth_session import get_auth_session_for_update
from app.core.security import create_access_token


REFRESH_TOKEN_DAYS = 7


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

def create_refresh_token(
    db: Session,
    user_id,
    session_id: UUID | None = None,
) -> str:
    raw_token = secrets.token_urlsafe(48)

    token_hash = hash_refresh_token(raw_token)

    expires_at = datetime.now(UTC) + timedelta(
        days=REFRESH_TOKEN_DAYS
    )

    refresh_token = RefreshToken(
        user_id=user_id,
        session_id=session_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    db.add(refresh_token)
    db.flush()

    return raw_token


class InvalidRefreshTokenError(Exception):
    pass

def rotate_refresh_token(
    db: Session,
    raw_token: str,
) -> tuple[str, str]:

    token_hash = hash_refresh_token(raw_token)

    statement = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )

    stored_token = db.execute(
        statement
    ).scalar_one_or_none()

    if stored_token is None:
        raise InvalidRefreshTokenError(
            "Invalid refresh token."
        )

    now = datetime.now(UTC)

    if stored_token.session_id is None:
        raise InvalidRefreshTokenError(
            "Refresh token has authentication session. Please log in again."
        )

    auth_session = get_auth_session_for_update(
        db=db,
        session_id=stored_token.session_id,
    )

    if auth_session is None:
        raise InvalidRefreshTokenError(
            "Authentication session not found."
        )

    if auth_session.user_id != stored_token.user_id:
        raise InvalidRefreshTokenError(
            "Refresh token does not belong to this session."
        )
    if auth_session.revoked_at is not None:
        raise InvalidRefreshTokenError(
            "Authentication session has been revoked."
        )

    if stored_token.expires_at <= now:
        raise InvalidRefreshTokenError(
            "Refresh token has expired"
        )

    user = db.get(User, stored_token.user_id)

    if user is None:
        raise InvalidRefreshTokenError(
            "User account not found."
        )

    if user.locked_until is not None and user.locked_until > now:
        raise InvalidRefreshTokenError(
            "User account is temporarily locked."
        )
    
    if user.kyc_status == KYCStatus.REJECTED:
        raise InvalidRefreshTokenError(
            "User account KYC has been rejected."
        )
    
    stored_token.revoked_at = now

    new_refresh_token = create_refresh_token(
        db=db,
        user_id=stored_token.user_id,
        session_id=auth_session.id,
    )

    new_access_token = create_access_token(
        user_id=stored_token.user_id,
        session_id=auth_session.id,
    )

    db.commit()

    return new_access_token, new_refresh_token