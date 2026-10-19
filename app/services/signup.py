from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Account, User
from app.repositories.account import generate_account_number
from app.repositories.user import get_user_by_email
from app.schemas.user import SignupRequest


def signup_user(
    db: Session,
    data: SignupRequest,
) -> tuple[User, Account]:

    existing_user = get_user_by_email(
        db=db,
        email=str(data.email),
    )

    if existing_user is not None:
        raise ValueError(
            "Email is already registered."
        )
    
    password_hash = hash_password(
        data.password
    )

    user = User(
        full_name=data.full_name,
        email=str(data.email),
        phone=data.phone,
        password_hash=password_hash,
        terms_accepted_at=datetime.now(UTC),
    )

    try:
        db.add(user)

        db.flush()

        account_number = generate_account_number(db=db)

        account = Account(
            user_id=user.id,
            account_number=account_number,
            currency="NGN",
        )

        db.add(account)

        db.flush()

        db.commit()

        db.refresh(user)
        db.refresh(account)

        return user, account

    except Exception:
        db.rollback()
        raise