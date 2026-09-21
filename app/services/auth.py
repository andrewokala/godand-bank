from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import KYCStatus, User
from app.repositories.user import create_user, get_user_by_email


MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def register_user(
    db: Session,
    full_name: str,
    email: str,
    phone: str,
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
        full_name=full_name,
        email=email,
        phone=phone,
        password_hash=password_hash,
        terms_accepted_at=datetime.now(UTC),
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

    now = datetime.now(UTC)

    if user.locked_until is not None and user.locked_until > now:
        raise ValueError("Account is temporarily locked.")

    if not verify_password(
        password,
        user.password_hash,
    ):
        user.failed_login_count += 1

        if user.failed_login_count >= MAX_FAILED_LOGIN_ATTEMPTS:
            from datetime import timedelta

            user.locked_until = now + timedelta(
                minutes=LOCKOUT_MINUTES,
            )

        db.commit()

        raise ValueError("Invalid email or password.")

    user.failed_login_count = 0
    user.locked_until = None

    db.commit()
    db.refresh(user)

    if user.kyc_status == KYCStatus.REJECTED:
        raise ValueError("Account KYC has been rejected.")

    return user
