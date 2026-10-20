from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession


def create_auth_session(
    db: Session,
    user_id: UUID,
) -> AuthSession:
    session = AuthSession(
        user_id=user_id,
    )

    db.add(session)
    db.flush()

    return session


def get_auth_session_for_update(
    db: Session,
    session_id: UUID,
) -> AuthSession | None:
    statement = (
        select(AuthSession)
        .where(AuthSession.id == session_id)
        .with_for_update()
    )

    return db.execute(statement).scalar_one_or_none()


def revoke_auth_session(
    db: Session,
    session_id: UUID,
) -> bool:
    session = get_auth_session_for_update(
        db=db,
        session_id=session_id,
    )

    if session is None:
        return False

    if session.revoked_at is not None:
        return False

    session.revoked_at = datetime.now(UTC)

    db.flush()

    return True