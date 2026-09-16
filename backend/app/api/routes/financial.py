"""Financial-operations demo workspace endpoints.

Educational / simplified only — see docs/security-and-limitations.md. Not
legal, tax, or regulatory advice.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_correlation_id, get_current_user, get_db
from app.models.enums import ClassificationStatus, DistributionKind, DistributionStatus, RegimeType
from app.models.financial import Classification, Distribution
from app.models.user import User
from app.schemas.common import Page
from app.schemas.financial import ClassificationOut, DistributionOut
from app.services.audit_log import record_audit

router = APIRouter()


@router.get("/classifications", response_model=Page[ClassificationOut])
def list_classifications(
    entity_id: int | None = None,
    regime: RegimeType | None = None,
    status_filter: ClassificationStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page:
    stmt = select(Classification)
    if entity_id:
        stmt = stmt.where(Classification.entity_id == entity_id)
    if regime:
        stmt = stmt.where(Classification.regime == regime)
    if status_filter:
        stmt = stmt.where(Classification.status == status_filter)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(Classification.id).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=list(rows), total=total, page=page, page_size=page_size)


@router.get("/distributions", response_model=Page[DistributionOut])
def list_distributions(
    kind: DistributionKind | None = None,
    status_filter: DistributionStatus | None = Query(None, alias="status"),
    entity_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page:
    stmt = select(Distribution)
    if kind:
        stmt = stmt.where(Distribution.kind == kind)
    if status_filter:
        stmt = stmt.where(Distribution.status == status_filter)
    if entity_id:
        stmt = stmt.where(Distribution.entity_id == entity_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(Distribution.id).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=list(rows), total=total, page=page, page_size=page_size)


@router.post("/distributions/{distribution_id}/mark-sent", response_model=DistributionOut)
def mark_distribution_sent(
    distribution_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Distribution:
    dist = db.get(Distribution, distribution_id)
    if dist is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Distribution not found")
    before = {"status": dist.status.value}
    dist.status = DistributionStatus.SENT
    dist.sent_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=user.id,
        entity_type="distribution",
        entity_id=dist.id,
        action="mark_sent",
        before=before,
        after={"status": dist.status.value},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(dist)
    return dist


@router.post("/distributions/{distribution_id}/acknowledge", response_model=DistributionOut)
def acknowledge_distribution(
    distribution_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Distribution:
    dist = db.get(Distribution, distribution_id)
    if dist is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Distribution not found")
    if dist.status != DistributionStatus.SENT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only sent distributions can be acknowledged"
        )
    before = {"status": dist.status.value}
    dist.status = DistributionStatus.ACKNOWLEDGED
    record_audit(
        db,
        actor_id=user.id,
        entity_type="distribution",
        entity_id=dist.id,
        action="acknowledge",
        before=before,
        after={"status": dist.status.value},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(dist)
    return dist
