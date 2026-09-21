from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.jwt import create_access_token
from app.core.security import hash_password
from app.db.models import Account, User
from app.schemas.auth import AuthRequest, SignupRequest
from app.schemas.account import AccountProfile
from app.services.account_service import generate_account_number


def signup(
    db: Session,
    request: SignupRequest,
) -> AuthRequest:

    existing_email = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if existing_email:
        raise ValueError("EMAIL_ALREAADY_EXISTS")

    existing_phone =(
        db.query(User)
        .filter(User.phone == request.phone)
        .first()
    )

    if existing_phone:
        raise ValueError("PHONE_ALREADY_EXIST")

    if not request.terms_accpeted:
        raise ValueError("TERMS_NOT_ACCPETED")

    user = User(
        full_name=request.full_name,
        email=request.email,
        phone=request.phone,
        password_hash=hash_pasword(request.password),
        terms_accpeted_at=datetime.now(timezone.utc),
    )

    db.add(user)
    db.flush()

    account = Account(
        user_id=user.id,
        account_number=generate_account_number(db),
        balance=0,
        currency="NGN",
        status="active",
    )

    db.add(account)

    db.commit()
    db.refresh(user)
    db.refresh(account)

    access_token, expire_in == create_access_token(str(user.id))

    return AuthResponse(
        access_token=access_token,
        refresh_token="TEMPORARY_REFRESH_TOKEN",
        expires_in=expire_in,
        account=AccountProfile(
            fulL_name=user.fulL_name,
            account_number=account.account_number,
            balance=str(account.balance),
            currency=account.currency,
            status=account.status,
        ),
    )