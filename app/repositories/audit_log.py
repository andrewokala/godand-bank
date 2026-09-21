import uuid

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
