from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.dependencies import get_db
from app.models import User
from app.repositories.audit_log import get_audit_logs_by_actor_user_id
from app.schemas.audit import AuditLogListResponse


router = APIRouter(
    prefix="/audit-logs",
    tags=["audit"],
)


@router.get(
    "",
    response_model=AuditLogListResponse,
)
def get_my_audit_logs(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logs, total = get_audit_logs_by_actor_user_id(
        db=db,
        actor_user_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    return {
        "items": logs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }