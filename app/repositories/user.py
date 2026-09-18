import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def create_user(
    db: Session,
    full_name: str,
    email: str,
    phone: str,
    password_hash: str,
    terms_accepted_at: datetime | None = None,
) -> User:
    user = User(
        full_name=full_name,
        email=email,
        phone=phone,
        password_hash=password_hash,
        terms_accepted_at=terms_accepted_at or datetime.now(UTC),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_user_by_id(
    db: Session,
    user_id: uuid.UUID,
) -> User | None:
    statement = select(User).where(User.id == user_id)

    return db.scalar(statement)


def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    statement = select(User).where(User.email == email)

    return db.scalar(statement)
