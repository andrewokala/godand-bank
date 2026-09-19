import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.repositories.audit_log import create_audit_log


def record_audit_event(
    db: Session,
    action: str,
    ip_address: str,
    metadata: dict,
    actor_user_id: uuid.UUID | None = None,
) -> AuditLog:
    return create_audit_log(
        db=db,
        action=action,
        ip_address=ip_address,
        metadata_json=metadata,
        actor_user_id=actor_user_id,
    )
