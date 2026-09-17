from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def create_user(
    db: Session,
    first_name: str,
    last_name: str,
    email: str,
    password_hash: str,
) -> User:
    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=password_hash,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_user_by_id(
    db: Session,
    user_id: int,
) -> User | None:
    statement = select(User).where(User.id == user_id)

    return db.scalar(statement)


def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    statement = select(User).where(User.email == email)

    return db.scalar(statement)
