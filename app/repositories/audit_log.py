import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog


def create_audit_log(
    db: Session,
    action: str,
    ip_address: str,
    metadata_json: dict,
    actor_user_id: uuid.UUID | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        ip_address=ip_address,
        metadata_json=metadata_json,
    )

    db.add(audit_log)


    db.flush()

    return audit_log

def get_audit_logs_by_actor_user_id(
    db: Session,
    actor_user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[AuditLog], int]:
    base_statement = select(AuditLog).where(
        AuditLog.actor_user_id == actor_user_id
    )

    total = db.scalar(
        select(func.count()).select_from(
            base_statement.subquery()
        )
    )

    statement = (
        base_statement
        .order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    logs = list(db.scalars(statement).all())

    return logs, total or 0