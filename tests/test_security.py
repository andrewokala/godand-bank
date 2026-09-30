from datetime import UTC, datetime, timedelta
from uuid import uuid4

from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token


def test_access_token_contains_required_claims():
    user_id = uuid4()

    token = create_access_token(user_id=user_id)

    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
    )

    assert payload["sub"] == str(user_id)
    assert "iat" in payload
    assert "exp" in payload
    assert "jti" in payload
    assert payload["type"] == "access"


def test_access_token_has_valid_issue_and_expiration_times():
    before = datetime.now(UTC)

    token = create_access_token(
        user_id=uuid4(),
        expires_minutes=30,
    )

    after = datetime.now(UTC)

    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
    )

    issued_at = datetime.fromtimestamp(payload["iat"], tz=UTC)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)

    assert before.replace(microsecond=0) <= issued_at <= after
    assert expires_at > issued_at
    assert expires_at - issued_at == timedelta(minutes=30)


def test_each_access_token_has_unique_jti():
    user_id = uuid4()

    first_token = create_access_token(user_id=user_id)
    second_token = create_access_token(user_id=user_id)

    first_payload = jwt.decode(
        first_token,
        settings.secret_key,
        algorithms=[settings.algorithm],
    )
    second_payload = jwt.decode(
        second_token,
        settings.secret_key,
        algorithms=[settings.algorithm],
    )

    assert first_payload["jti"] != second_payload["jti"]
