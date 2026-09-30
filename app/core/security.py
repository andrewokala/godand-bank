from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    user_id: UUID,
    expires_minutes: int = 30,
) -> str:
    issued_at = datetime.now(UTC)
    expire = issued_at + timedelta(
        minutes=expires_minutes,
    )

    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": expire,
        "jti": str(uuid4()),
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
