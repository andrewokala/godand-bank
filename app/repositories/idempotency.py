from datetime import UTC, datetime, timedelta
import uuid

from sqlalchemy.orm import Session

from app.models import IdempotencyKey


IDEMPOTENCY_TTL = timedelta(hours=24)


def get_idempotency_key(
    db: Session,
    key: str,
) -> IdempotencyKey | None:
    return db.get(IdempotencyKey, key)


def reserve_idempotency_key(
    db: Session,
    key: str,
    user_id: uuid.UUID,
    request_hash: str,
) -> IdempotencyKey:
    now = datetime.now(UTC)

    record = IdempotencyKey(
        key=key,
        user_id=user_id,
        request_hash=request_hash,
        response_snapshot={},
        created_at=now,
        expires_at=now + IDEMPOTENCY_TTL,
    )

    db.add(record)
    db.flush()

    return record


def store_response_snapshot(
    record: IdempotencyKey,
    response_snapshot: dict,
) -> None:
    record.response_snapshot = response_snapshot
