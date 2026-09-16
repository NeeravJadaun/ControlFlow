from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.audit import AuditLog
from app.models.enums import Role
from app.models.user import User
from app.schemas.audit import AuditLogOut
from app.schemas.common import Page

router = APIRouter()


@router.get("", response_model=Page[AuditLogOut])
def list_audit_log(
    entity_type: str | None = None,
    entity_id: int | None = None,
    actor_id: int | None = None,
    since: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(Role.AUDITOR, Role.COMPLIANCE_OFFICER)),
) -> Page:
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if since:
        stmt = stmt.where(AuditLog.timestamp >= since)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(AuditLog.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        .scalars()
        .all()
    )
    return Page(items=list(rows), total=total, page=page, page_size=page_size)


@router.get("/entity/{entity_type}/{entity_id}", response_model=list[AuditLogOut])
def entity_audit_trail(
    entity_type: str,
    entity_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[AuditLog]:
    """Any authenticated user can see the audit trail for a specific record they're viewing."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.timestamp)
    )
    return list(db.execute(stmt).scalars().all())
