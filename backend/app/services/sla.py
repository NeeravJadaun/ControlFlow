"""Pure SLA calculation logic (no DB access) — kept side-effect free for unit tests."""

from datetime import UTC, datetime, timedelta

from app.models.enums import CasePriority, CaseStatus

TERMINAL_STATUSES = {CaseStatus.RESOLVED, CaseStatus.CLOSED}

OPEN_STATUSES = [
    CaseStatus.OPEN,
    CaseStatus.IN_PROGRESS,
    CaseStatus.PENDING_REVIEW,
    CaseStatus.ESCALATED,
]

PRIORITY_MULTIPLIER = {
    CasePriority.CRITICAL: 0.25,
    CasePriority.HIGH: 0.5,
    CasePriority.MEDIUM: 1.0,
    CasePriority.LOW: 2.0,
}


def compute_due_at(
    created_at: datetime, sla_hours: int, priority: CasePriority = CasePriority.MEDIUM
) -> datetime:
    """SLA deadline scales with priority: critical cases get a quarter of the base window."""
    multiplier = PRIORITY_MULTIPLIER[priority]
    return created_at + timedelta(hours=sla_hours * multiplier)


def is_breached(
    status: CaseStatus,
    due_at: datetime | None,
    resolved_at: datetime | None,
    as_of: datetime | None = None,
) -> bool:
    """A case is SLA-breached if it's still open past due_at, or was resolved after due_at."""
    if due_at is None:
        return False
    as_of = as_of or datetime.now(UTC)
    if status in TERMINAL_STATUSES:
        return resolved_at is not None and resolved_at > due_at
    return as_of > due_at


def hours_overdue(due_at: datetime | None, as_of: datetime | None = None) -> float:
    if due_at is None:
        return 0.0
    as_of = as_of or datetime.now(UTC)
    delta = (as_of - due_at).total_seconds() / 3600
    return max(delta, 0.0)


def attainment_rate(total_resolved: int, resolved_within_sla: int) -> float:
    """Percentage of resolved cases that met their SLA. Returns 100.0 when nothing resolved yet."""
    if total_resolved == 0:
        return 100.0
    return round((resolved_within_sla / total_resolved) * 100, 2)
