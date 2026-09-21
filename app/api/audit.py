from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models import User
from app.repositories.audit_log import get_audit_logs_by_actor_user_id
from app.schemas.audit import AuditLogResponse


router = APIRouter(
    prefix="/audit-logs",
    tags=["audit"],
)


@router.get(
    "",
    response_model=list[AuditLogResponse],
)
def get_my_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_audit_logs_by_actor_user_id(
        db=db,
        actor_user_id=current_user.id,
    )
