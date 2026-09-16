"""Immutable audit-trail writer. AuditLog rows are never updated or deleted."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_audit(
    db: Session,
    *,
    actor_id: int | None,
    entity_type: str,
    entity_id: int,
    action: str,
    before: dict | None = None,
    after: dict | None = None,
    correlation_id: str | None = None,
    timestamp: datetime | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        timestamp=timestamp or datetime.now(UTC),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before=before,
        after=after,
        correlation_id=correlation_id,
    )
    db.add(entry)
    return entry
