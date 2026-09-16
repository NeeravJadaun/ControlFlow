import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.deps import get_correlation_id, get_current_user, get_db
from app.models.entity import Account, Contact, Entity, RecordType
from app.models.enums import EntityKind
from app.models.user import User
from app.schemas.common import Page
from app.schemas.entity import (
    AccountOut,
    ContactOut,
    EntityCreate,
    EntityOut,
    EntityUpdate,
    RecordTypeOut,
)
from app.services.audit_log import record_audit

router = APIRouter()


@router.get("/record-types", response_model=list[RecordTypeOut])
def list_record_types(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[RecordType]:
    return list(db.execute(select(RecordType).order_by(RecordType.name)).scalars().all())


@router.get("", response_model=Page[EntityOut])
def list_entities(
    kind: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    owner_id: int | None = None,
    jurisdiction: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Page:
    stmt = select(Entity)
    if kind:
        stmt = stmt.where(Entity.kind == kind)
    if status_filter:
        stmt = stmt.where(Entity.status == status_filter)
    if owner_id:
        stmt = stmt.where(Entity.owner_id == owner_id)
    if jurisdiction:
        stmt = stmt.where(Entity.jurisdiction == jurisdiction)
    if q:
        stmt = stmt.where(Entity.name.ilike(f"%{q}%"))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(stmt.order_by(Entity.id).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=list(rows), total=total, page=page, page_size=page_size)


@router.get("/export.csv")
def export_entities_csv(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> StreamingResponse:
    rows = db.execute(select(Entity).order_by(Entity.id)).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["id", "kind", "name", "status", "priority", "jurisdiction", "owner_id", "created_at"]
    )
    for e in rows:
        writer.writerow(
            [
                e.id,
                e.kind.value,
                e.name,
                e.status,
                e.priority,
                e.jurisdiction,
                e.owner_id,
                e.created_at,
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=entities.csv"},
    )


@router.post("/import")
async def import_entities_csv(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> dict:
    """Bulk-create entities from a CSV with columns: kind,name,record_type_key,
    external_ref,status,priority,jurisdiction. Unknown/missing record_type_key
    rows are rejected individually; valid rows are still committed.
    """
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    record_types = {rt.key: rt for rt in db.execute(select(RecordType)).scalars().all()}

    created = 0
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):  # row 1 is the header
        try:
            kind = EntityKind(row["kind"].strip())
            record_type = record_types.get(row.get("record_type_key", "").strip() or kind.value)
            if record_type is None:
                errors.append(f"Row {i}: unknown record_type_key '{row.get('record_type_key')}'")
                continue
            entity = Entity(
                record_type_id=record_type.id,
                kind=kind,
                name=row["name"].strip(),
                external_ref=row.get("external_ref") or None,
                status=row.get("status") or "active",
                priority=row.get("priority") or "medium",
                jurisdiction=row.get("jurisdiction") or None,
            )
            db.add(entity)
            db.flush()
            created += 1
        except (KeyError, ValueError) as exc:
            errors.append(f"Row {i}: {exc}")

    if created:
        record_audit(
            db,
            actor_id=user.id,
            entity_type="entity",
            entity_id=0,
            action="bulk_import",
            after={"created": created, "errors": len(errors)},
            correlation_id=correlation_id,
        )
    db.commit()
    return {"created": created, "errors": errors}


@router.get("/{entity_id}", response_model=EntityOut)
def get_entity(
    entity_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> Entity:
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found")
    return entity


@router.get("/{entity_id}/accounts", response_model=list[AccountOut])
def get_entity_accounts(
    entity_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[Account]:
    return list(db.execute(select(Account).where(Account.entity_id == entity_id)).scalars().all())


@router.get("/{entity_id}/contacts", response_model=list[ContactOut])
def get_entity_contacts(
    entity_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[Contact]:
    return list(db.execute(select(Contact).where(Contact.entity_id == entity_id)).scalars().all())


@router.post("", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
def create_entity(
    payload: EntityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Entity:
    entity = Entity(**payload.model_dump())
    db.add(entity)
    db.flush()
    record_audit(
        db,
        actor_id=user.id,
        entity_type="entity",
        entity_id=entity.id,
        action="create",
        after=payload.model_dump(mode="json"),
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(entity)
    return entity


@router.patch("/{entity_id}", response_model=EntityOut)
def update_entity(
    entity_id: int,
    payload: EntityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> Entity:
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found")
    if entity.version != payload.version:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Entity was modified by someone else; reload and retry (optimistic lock failure)",
        )
    before = {
        "name": entity.name,
        "status": entity.status,
        "priority": entity.priority,
        "owner_id": entity.owner_id,
    }
    updates = payload.model_dump(exclude={"version"}, exclude_unset=True)
    for field, value in updates.items():
        setattr(entity, field, value)
    try:
        db.flush()
    except StaleDataError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Optimistic lock failure") from exc

    record_audit(
        db,
        actor_id=user.id,
        entity_type="entity",
        entity_id=entity.id,
        action="update",
        before=before,
        after=updates,
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(entity)
    return entity
