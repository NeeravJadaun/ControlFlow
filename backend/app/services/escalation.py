"""Case escalation: decision logic plus the DB-mutating apply step."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.audit import EscalationRule
from app.models.case import Case, CaseComment
from app.models.enums import CasePriority, CaseStatus, Role, WorkflowEntityType
from app.services import sla
from app.services.audit_log import record_audit
from app.services.workflow_engine import apply_transition, get_workflow

SYSTEM_ACTOR_ID = None  # background jobs act as "system" (no human actor)
CASE_WORKFLOW_KEY = "case-lifecycle"


def should_escalate(case: Case, rule: EscalationRule, as_of: datetime | None = None) -> bool:
    if not rule.is_active:
        return False
    if case.status in sla.TERMINAL_STATUSES:
        return False
    overdue_hours = sla.hours_overdue(case.due_at, as_of)
    return overdue_hours >= rule.overdue_hours_threshold


def apply_escalation(db: Session, case: Case, rule: EscalationRule, correlation_id: str) -> Case:
    before = {"status": case.status.value, "escalation_level": case.escalation_level}

    case.escalation_level += 1
    case.status = CaseStatus.ESCALATED
    if case.priority != CasePriority.CRITICAL:
        case.priority = CasePriority.HIGH

    comment = CaseComment(
        case_id=case.id,
        author_id=SYSTEM_ACTOR_ID,
        body=(
            f"Auto-escalated by rule '{rule.key}': overdue past "
            f"{rule.overdue_hours_threshold}h threshold. Escalation level {case.escalation_level}."
        ),
    )
    db.add(comment)

    workflow = get_workflow(db, CASE_WORKFLOW_KEY)
    apply_transition(
        db,
        workflow,
        WorkflowEntityType.CASE,
        case.id,
        transition_key="escalate",
        actor_role=Role.ADMIN,
        actor_id=SYSTEM_ACTOR_ID,
        comment=f"Auto-escalated by rule '{rule.key}'",
    )

    after = {"status": case.status.value, "escalation_level": case.escalation_level}
    record_audit(
        db,
        actor_id=SYSTEM_ACTOR_ID,
        entity_type="case",
        entity_id=case.id,
        action="auto_escalate",
        before=before,
        after=after,
        correlation_id=correlation_id,
        timestamp=datetime.now(UTC),
    )
    return case
