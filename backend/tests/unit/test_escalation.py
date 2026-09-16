from datetime import UTC, datetime, timedelta

from app.models.audit import EscalationRule
from app.models.case import Case
from app.models.enums import CaseStatus
from app.services import escalation


def make_rule(threshold_hours=24, active=True) -> EscalationRule:
    return EscalationRule(
        key="test-rule",
        applies_to="case",
        overdue_hours_threshold=threshold_hours,
        action="escalate",
        is_active=active,
    )


def make_case(status=CaseStatus.OPEN, due_at=None) -> Case:
    case = Case(queue_id=1, title="Test case", status=status, due_at=due_at)
    return case


def test_should_escalate_when_overdue_past_threshold():
    now = datetime(2026, 1, 5, tzinfo=UTC)
    due = now - timedelta(hours=30)
    case = make_case(due_at=due)
    rule = make_rule(threshold_hours=24)
    assert escalation.should_escalate(case, rule, now) is True


def test_should_not_escalate_when_within_threshold():
    now = datetime(2026, 1, 5, tzinfo=UTC)
    due = now - timedelta(hours=10)
    case = make_case(due_at=due)
    rule = make_rule(threshold_hours=24)
    assert escalation.should_escalate(case, rule, now) is False


def test_should_not_escalate_inactive_rule():
    now = datetime(2026, 1, 5, tzinfo=UTC)
    due = now - timedelta(hours=100)
    case = make_case(due_at=due)
    rule = make_rule(threshold_hours=24, active=False)
    assert escalation.should_escalate(case, rule, now) is False


def test_should_not_escalate_terminal_status():
    now = datetime(2026, 1, 5, tzinfo=UTC)
    due = now - timedelta(hours=100)
    case = make_case(status=CaseStatus.RESOLVED, due_at=due)
    rule = make_rule(threshold_hours=24)
    assert escalation.should_escalate(case, rule, now) is False


def test_should_not_escalate_without_due_date():
    now = datetime(2026, 1, 5, tzinfo=UTC)
    case = make_case(due_at=None)
    rule = make_rule(threshold_hours=24)
    assert escalation.should_escalate(case, rule, now) is False
