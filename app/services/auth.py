from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories.user import create_user, get_user_by_email


def register_user(
    db: Session,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
) -> User:
    existing_user = get_user_by_email(
        db=db,
        email=email,
    )

    if existing_user is not None:
        raise ValueError("Email is already registered.")

    password_hash = hash_password(password)

    return create_user(
        db=db,
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=password_hash,
    )


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User:
    user = get_user_by_email(
        db=db,
        email=email,
    )

    if user is None:
        raise ValueError("Invalid email or password.")

    if not verify_password(
        password,
        user.password_hash,
    ):
        raise ValueError("Invalid email or password.")

    return user