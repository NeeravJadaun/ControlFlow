import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.deps import get_correlation_id, get_current_user, get_db
from app.models.case import Case, CaseAttachment, CaseComment, CaseQueue, SavedView
from app.models.enums import CasePriority, CaseStatus, WorkflowEntityType
from app.models.user import User
from app.schemas.case import (
    BulkUpdateRequest,
    CaseAttachmentCreate,
    CaseAttachmentOut,
    CaseCommentCreate,
    CaseCommentOut,
    CaseCreate,
    CaseOut,
    CaseQueueOut,
    CaseResolve,
    CaseUpdate,
    SavedViewCreate,
    SavedViewOut,
)
from app.schemas.common import Page
from app.services import sla
from app.services.audit_log import record_audit
from app.services.workflow_engine import (
    ForbiddenTransitionError,
    InvalidTransitionError,
    MissingFieldsError,
    apply_transition,
    get_workflow,
    initiate,
)

router = APIRouter()

CASE_WORKFLOW_KEY = "case-lifecycle"


@router.get("", response_model=Page[CaseOut])
def list_cases(
    queue_id: int | None = None,
    status_filter: CaseStatus | None = Query(None, alias="status"),
    priority: CasePriority | None = None,
    owner_id: int | None = None,
    entity_id: int | None = None,
    overdue_only: bool = False,
    open_only: bool = False,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page:
    stmt = select(Case)
    if queue_id:
        stmt = stmt.where(Case.queue_id == queue_id)
    if status_filter:
        stmt = stmt.where(Case.status == status_filter)
    if priority:
        stmt = stmt.where(Case.priority == priority)
    if owner_id:
        stmt = stmt.where(Case.owner_id == owner_id)
    if entity_id:
        stmt = stmt.where(Case.entity_id == entity_id)
    if open_only:
        # Matches the dashboard's open_and_overdue_cases / by_priority scope, so
        # tiles built from that metric drill down into exactly this same set.
        stmt = stmt.where(Case.status.in_(sla.OPEN_STATUSES))
    if overdue_only:
        # Live overdue check (matches the dashboard's open_and_overdue_cases metric)
        # rather than the batch-computed `sla_breached` flag, which only reflects
        # the state as of the last daily monitoring run.
        stmt = stmt.where(
            Case.status.in_(sla.OPEN_STATUSES),
            Case.due_at.is_not(None),
            Case.due_at < datetime.now(UTC),
        )
    if q:
        stmt = stmt.where(Case.title.ilike(f"%{q}%"))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(Case.id.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=list(rows), total=total, page=page, page_size=page_size)


@router.get("/queues", response_model=list[CaseQueueOut])
def list_case_queues(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[CaseQueue]:
    return list(db.execute(select(CaseQueue).order_by(CaseQueue.name)).scalars().all())


@router.get("/export.csv")
def export_cases_csv(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> StreamingResponse:
    rows = db.execute(select(Case).order_by(Case.id)).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "title",
            "status",
            "priority",
            "owner_id",
            "due_at",
            "sla_breached",
            "escalation_level",
        ]
    )
    for c in rows:
        writer.writerow(
            [
                c.id,
                c.title,
                c.status.value,
                c.priority.value,
                c.owner_id,
                c.due_at,
                c.sla_breached,
                c.escalation_level,
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cases.csv"},
    )


@router.post("/import")
async def import_cases_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> dict:
    """Bulk-create cases from a CSV with columns: queue_key,title,description,
    case_type,priority,entity_id. Each valid row goes through the same
    creation path (SLA due-date calculation, workflow initiation) as a
    single-case POST.
    """
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    queues = {q.key: q for q in db.execute(select(CaseQueue)).scalars().all()}
    workflow = get_workflow(db, CASE_WORKFLOW_KEY)

    created = 0
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        try:
            queue = queues.get(row["queue_key"].strip())
            if queue is None:
                errors.append(f"Row {i}: unknown queue_key '{row.get('queue_key')}'")
                continue
            priority = CasePriority(row.get("priority", "medium").strip() or "medium")
            due_at = sla.compute_due_at(datetime.now(UTC), queue.default_sla_hours, priority)
            case = Case(
                queue_id=queue.id,
                entity_id=int(row["entity_id"]) if row.get("entity_id") else None,
                title=row["title"].strip(),
                description=row.get("description") or None,
                case_type=row.get("case_type") or "general",
                priority=priority,
                owner_id=user.id,
                due_at=due_at,
            )
            db.add(case)
            db.flush()
            initiate(
                db,
                workflow,
                WorkflowEntityType.CASE,
                case.id,
                actor_id=user.id,
                comment="Imported case",
            )
            created += 1
        except (KeyError, ValueError) as exc:
            errors.append(f"Row {i}: {exc}")

    if created:
        record_audit(
            db,
            actor_id=user.id,
            entity_type="case",
            entity_id=0,
            action="bulk_import",
            after={"created": created, "errors": len(errors)},
            correlation_id=correlation_id,
        )
    db.commit()
    return {"created": created, "errors": errors}


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    case_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Case:
    queue = db.get(CaseQueue, payload.queue_id)
    if queue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case queue not found")
    due_at = sla.compute_due_at(datetime.now(UTC), queue.default_sla_hours, payload.priority)
    case = Case(
        queue_id=payload.queue_id,
        entity_id=payload.entity_id,
        title=payload.title,
        description=payload.description,
        case_type=payload.case_type,
        priority=payload.priority,
        owner_id=user.id,
        due_at=due_at,
    )
    db.add(case)
    db.flush()

    workflow = get_workflow(db, CASE_WORKFLOW_KEY)
    initiate(
        db, workflow, WorkflowEntityType.CASE, case.id, actor_id=user.id, comment="Case created"
    )

    record_audit(
        db,
        actor_id=user.id,
        entity_type="case",
        entity_id=case.id,
        action="create",
        after={"title": case.title, "status": case.status.value},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(case)
    return case


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(
    case_id: int,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    if case.version != payload.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "Optimistic lock failure")

    before = {"title": case.title, "owner_id": case.owner_id, "priority": case.priority.value}
    updates = payload.model_dump(exclude={"version", "status"}, exclude_unset=True)
    for field, value in updates.items():
        setattr(case, field, value)
    try:
        db.flush()
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Optimistic lock failure") from exc

    record_audit(
        db,
        actor_id=user.id,
        entity_type="case",
        entity_id=case.id,
        action="update",
        before=before,
        after=updates,
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(case)
    return case


def _do_case_transition(
    db: Session,
    case: Case,
    transition_key: str,
    to_status: CaseStatus,
    user: User,
    comment: str | None,
    correlation_id: str,
) -> Case:
    workflow = get_workflow(db, CASE_WORKFLOW_KEY)
    try:
        apply_transition(
            db,
            workflow,
            WorkflowEntityType.CASE,
            case.id,
            transition_key=transition_key,
            actor_role=user.role,
            actor_id=user.id,
            comment=comment,
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ForbiddenTransitionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except MissingFieldsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    before = {"status": case.status.value}
    case.status = to_status
    record_audit(
        db,
        actor_id=user.id,
        entity_type="case",
        entity_id=case.id,
        action=transition_key,
        before=before,
        after={"status": to_status.value},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(case)
    return case


@router.post("/{case_id}/start", response_model=CaseOut)
def start_case(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return _do_case_transition(
        db, case, "start", CaseStatus.IN_PROGRESS, user, "Work started", correlation_id
    )


@router.post("/{case_id}/submit-for-review", response_model=CaseOut)
def submit_case_for_review(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return _do_case_transition(
        db,
        case,
        "submit_for_review",
        CaseStatus.PENDING_REVIEW,
        user,
        "Submitted for review",
        correlation_id,
    )


@router.post("/{case_id}/resolve", response_model=CaseOut)
def resolve_case(
    case_id: int,
    payload: CaseResolve,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    if case.version != payload.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "Optimistic lock failure")

    workflow = get_workflow(db, CASE_WORKFLOW_KEY)
    try:
        apply_transition(
            db,
            workflow,
            WorkflowEntityType.CASE,
            case.id,
            transition_key="resolve",
            actor_role=user.role,
            actor_id=user.id,
            provided_fields={"resolution_evidence": payload.resolution_evidence},
            comment="Case resolved",
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ForbiddenTransitionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except MissingFieldsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    before = {"status": case.status.value}
    now = datetime.now(UTC)
    case.status = CaseStatus.RESOLVED
    case.resolution_evidence = payload.resolution_evidence
    case.resolved_at = now
    case.sla_breached = sla.is_breached(CaseStatus.RESOLVED, case.due_at, now, now)
    record_audit(
        db,
        actor_id=user.id,
        entity_type="case",
        entity_id=case.id,
        action="resolve",
        before=before,
        after={"status": case.status.value},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(case)
    return case


@router.post("/{case_id}/escalate", response_model=CaseOut)
def escalate_case(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    case.escalation_level += 1
    if case.priority != CasePriority.CRITICAL:
        case.priority = CasePriority.HIGH
    return _do_case_transition(
        db, case, "escalate", CaseStatus.ESCALATED, user, "Manually escalated", correlation_id
    )


@router.post("/{case_id}/close", response_model=CaseOut)
def close_case(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return _do_case_transition(
        db, case, "close", CaseStatus.CLOSED, user, "Case closed", correlation_id
    )


@router.post("/{case_id}/reopen", response_model=CaseOut)
def reopen_case(
    case_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    case.resolved_at = None
    return _do_case_transition(
        db, case, "reopen", CaseStatus.OPEN, user, "Case reopened", correlation_id
    )


@router.get("/{case_id}/comments", response_model=list[CaseCommentOut])
def list_comments(
    case_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[CaseComment]:
    return list(
        db.execute(
            select(CaseComment)
            .where(CaseComment.case_id == case_id)
            .order_by(CaseComment.created_at)
        )
        .scalars()
        .all()
    )


@router.post(
    "/{case_id}/comments", response_model=CaseCommentOut, status_code=status.HTTP_201_CREATED
)
def add_comment(
    case_id: int,
    payload: CaseCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseComment:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    comment = CaseComment(case_id=case_id, author_id=user.id, body=payload.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/{case_id}/attachments", response_model=list[CaseAttachmentOut])
def list_attachments(
    case_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[CaseAttachment]:
    return list(
        db.execute(select(CaseAttachment).where(CaseAttachment.case_id == case_id)).scalars().all()
    )


@router.post(
    "/{case_id}/attachments", response_model=CaseAttachmentOut, status_code=status.HTTP_201_CREATED
)
def add_attachment_metadata(
    case_id: int,
    payload: CaseAttachmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CaseAttachment:
    """Records attachment metadata only (demo scope stores no binary content)."""
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    safe_name = payload.filename.replace("/", "_").replace("\\", "_")
    attachment = CaseAttachment(
        case_id=case_id,
        filename=safe_name,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        storage_ref=f"demo://case-{case_id}/{safe_name}",
        uploaded_by_id=user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@router.post("/bulk-update", response_model=list[CaseOut])
def bulk_update_cases(
    payload: BulkUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> list[Case]:
    cases = db.execute(select(Case).where(Case.id.in_(payload.case_ids))).scalars().all()
    for case in cases:
        before = {
            "status": case.status.value,
            "priority": case.priority.value,
            "owner_id": case.owner_id,
        }
        if payload.status is not None:
            case.status = payload.status
        if payload.priority is not None:
            case.priority = payload.priority
        if payload.owner_id is not None:
            case.owner_id = payload.owner_id
        record_audit(
            db,
            actor_id=user.id,
            entity_type="case",
            entity_id=case.id,
            action="bulk_update",
            before=before,
            after={
                "status": case.status.value,
                "priority": case.priority.value,
                "owner_id": case.owner_id,
            },
            correlation_id=correlation_id,
        )
    db.commit()
    return list(cases)


@router.get("/views/saved", response_model=list[SavedViewOut])
def list_saved_views(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[SavedView]:
    return list(db.execute(select(SavedView).where(SavedView.owner_id == user.id)).scalars().all())


@router.post("/views/saved", response_model=SavedViewOut, status_code=status.HTTP_201_CREATED)
def create_saved_view(
    payload: SavedViewCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SavedView:
    view = SavedView(
        owner_id=user.id,
        name=payload.name,
        entity_type=payload.entity_type,
        filters=payload.filters,
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    return view
