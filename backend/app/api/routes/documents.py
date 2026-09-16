import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_correlation_id, get_current_user, get_db, require_roles
from app.models.document import Document, DocumentType
from app.models.enums import ReviewStatus, Role, WorkflowEntityType
from app.models.user import User
from app.schemas.common import Page
from app.schemas.document import (
    DocumentApprove,
    DocumentCreate,
    DocumentOut,
    DocumentReject,
    DocumentTypeOut,
)
from app.services import renewal
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

DOCUMENT_WORKFLOW_KEY = "document-approval"


@router.get("/types", response_model=list[DocumentTypeOut])
def list_document_types(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[DocumentType]:
    return list(db.execute(select(DocumentType).order_by(DocumentType.name)).scalars().all())


@router.get("", response_model=Page[DocumentOut])
def list_documents(
    entity_id: int | None = None,
    document_type_id: int | None = None,
    review_status: ReviewStatus | None = None,
    jurisdiction: str | None = None,
    expiring_within_days: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page:
    stmt = select(Document)
    if entity_id:
        stmt = stmt.where(Document.entity_id == entity_id)
    if document_type_id:
        stmt = stmt.where(Document.document_type_id == document_type_id)
    if review_status:
        stmt = stmt.where(Document.review_status == review_status)
    if jurisdiction:
        stmt = stmt.where(Document.jurisdiction == jurisdiction)
    if expiring_within_days is not None:
        # Matches the dashboard's expiring_within_window metric: not-yet-expired
        # documents landing inside the window, excluding ones already expired.
        today = date.today()
        horizon = today + timedelta(days=expiring_within_days)
        stmt = stmt.where(
            Document.expiry_date.is_not(None),
            Document.expiry_date >= today,
            Document.expiry_date <= horizon,
        )

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(Document.id).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=list(rows), total=total, page=page, page_size=page_size)


@router.get("/export.csv")
def export_documents_csv(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> StreamingResponse:
    rows = db.execute(select(Document).order_by(Document.id)).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "entity_id",
            "document_type_id",
            "review_status",
            "issue_date",
            "expiry_date",
            "completeness_score",
            "is_duplicate_of_id",
        ]
    )
    for d in rows:
        writer.writerow(
            [
                d.id,
                d.entity_id,
                d.document_type_id,
                d.review_status.value,
                d.issue_date,
                d.expiry_date,
                d.completeness_score,
                d.is_duplicate_of_id,
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=documents.csv"},
    )


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Document:
    doc_type = db.get(DocumentType, payload.document_type_id)
    if doc_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document type not found")

    score, missing = renewal.compute_completeness(doc_type.required_fields, payload.provided_fields)
    checksum = renewal.compute_checksum(
        entity_id=payload.entity_id, document_type_key=doc_type.key, issue_date=payload.issue_date
    )
    duplicate = db.execute(
        select(Document).where(
            Document.checksum == checksum, Document.entity_id == payload.entity_id
        )
    ).scalar_one_or_none()

    doc = Document(
        document_type_id=payload.document_type_id,
        entity_id=payload.entity_id,
        jurisdiction=payload.jurisdiction,
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        file_ref=payload.file_ref,
        classification=payload.classification,
        checksum=checksum,
        completeness_score=score,
        missing_fields=missing,
        is_duplicate_of_id=duplicate.id if duplicate else None,
        uploaded_by_id=user.id,
        review_status=ReviewStatus.DRAFT,
    )
    db.add(doc)
    db.flush()

    workflow = get_workflow(db, DOCUMENT_WORKFLOW_KEY)
    initiate(
        db,
        workflow,
        WorkflowEntityType.DOCUMENT,
        doc.id,
        actor_id=user.id,
        comment="Document created",
    )

    record_audit(
        db,
        actor_id=user.id,
        entity_type="document",
        entity_id=doc.id,
        action="create",
        after={"review_status": doc.review_status.value, "completeness_score": score},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(doc)
    return doc


def _transition_document(
    db: Session,
    doc: Document,
    transition_key: str,
    to_status: ReviewStatus,
    user: User,
    comment: str | None,
    correlation_id: str,
) -> Document:
    workflow = get_workflow(db, DOCUMENT_WORKFLOW_KEY)
    try:
        apply_transition(
            db,
            workflow,
            WorkflowEntityType.DOCUMENT,
            doc.id,
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

    before = {"review_status": doc.review_status.value}
    doc.review_status = to_status
    if to_status == ReviewStatus.APPROVED:
        doc.approver_id = user.id
    record_audit(
        db,
        actor_id=user.id,
        entity_type="document",
        entity_id=doc.id,
        action=transition_key,
        before=before,
        after={"review_status": to_status.value},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/{document_id}/submit", response_model=DocumentOut)
def submit_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if doc.completeness_score < 100:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Document is incomplete (missing fields: {', '.join(doc.missing_fields)})",
        )
    return _transition_document(
        db, doc, "submit", ReviewStatus.PENDING_REVIEW, user, "Submitted for review", correlation_id
    )


@router.post("/{document_id}/approve", response_model=DocumentOut)
def approve_document(
    document_id: int,
    payload: DocumentApprove,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.REVIEWER, Role.COMPLIANCE_OFFICER)),
    correlation_id: str = Depends(get_correlation_id),
) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if doc.version != payload.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "Optimistic lock failure")
    return _transition_document(
        db, doc, "approve", ReviewStatus.APPROVED, user, payload.comment, correlation_id
    )


@router.post("/{document_id}/reject", response_model=DocumentOut)
def reject_document(
    document_id: int,
    payload: DocumentReject,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.REVIEWER, Role.COMPLIANCE_OFFICER)),
    correlation_id: str = Depends(get_correlation_id),
) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if doc.version != payload.version:
        raise HTTPException(status.HTTP_409_CONFLICT, "Optimistic lock failure")
    return _transition_document(
        db, doc, "reject", ReviewStatus.REJECTED, user, payload.reason, correlation_id
    )


@router.post(
    "/{document_id}/renew", response_model=DocumentOut, status_code=status.HTTP_201_CREATED
)
def renew_document(
    document_id: int,
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Document:
    """Create a new version of a document, superseding the given one."""
    prior = db.get(Document, document_id)
    if prior is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    doc_type = db.get(DocumentType, prior.document_type_id)
    if doc_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document type not found")
    score, missing = renewal.compute_completeness(doc_type.required_fields, payload.provided_fields)
    checksum = renewal.compute_checksum(
        entity_id=prior.entity_id, document_type_key=doc_type.key, issue_date=payload.issue_date
    )
    new_doc = Document(
        document_type_id=prior.document_type_id,
        entity_id=prior.entity_id,
        jurisdiction=payload.jurisdiction or prior.jurisdiction,
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        version_number=prior.version_number + 1,
        file_ref=payload.file_ref,
        classification=payload.classification or prior.classification,
        checksum=checksum,
        completeness_score=score,
        missing_fields=missing,
        uploaded_by_id=user.id,
        review_status=ReviewStatus.DRAFT,
    )
    db.add(new_doc)
    db.flush()
    workflow = get_workflow(db, DOCUMENT_WORKFLOW_KEY)
    initiate(
        db,
        workflow,
        WorkflowEntityType.DOCUMENT,
        new_doc.id,
        actor_id=user.id,
        comment=f"Renewal of document #{prior.id}",
    )
    record_audit(
        db,
        actor_id=user.id,
        entity_type="document",
        entity_id=new_doc.id,
        action="renew",
        before={"prior_document_id": prior.id},
        after={"version_number": new_doc.version_number},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(new_doc)
    return new_doc
