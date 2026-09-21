from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


def create_access_token(user_id: str) -> tuple[str, int]:
    expires_in = settings.jwt_access_token_expire_minutes * 60

    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=expire_in,
    )

    payload = {
        "sub": user_id,
        "type": "access",
        "exp": expires_at,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    return token, expires_in