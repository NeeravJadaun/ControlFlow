from datetime import UTC, datetime, timedelta

from app.models.enums import CasePriority, CaseStatus
from app.services import sla


def test_compute_due_at_scales_with_priority():
    created = datetime(2026, 1, 1, tzinfo=UTC)
    medium_due = sla.compute_due_at(created, 48, CasePriority.MEDIUM)
    critical_due = sla.compute_due_at(created, 48, CasePriority.CRITICAL)
    low_due = sla.compute_due_at(created, 48, CasePriority.LOW)

    assert medium_due == created + timedelta(hours=48)
    assert critical_due == created + timedelta(hours=12)  # 48 * 0.25
    assert low_due == created + timedelta(hours=96)  # 48 * 2.0
    assert critical_due < medium_due < low_due


def test_is_breached_open_case_past_due():
    due = datetime(2026, 1, 1, tzinfo=UTC)
    now = due + timedelta(hours=1)
    assert sla.is_breached(CaseStatus.OPEN, due, None, now) is True


def test_is_breached_open_case_not_yet_due():
    due = datetime(2026, 1, 1, tzinfo=UTC)
    now = due - timedelta(hours=1)
    assert sla.is_breached(CaseStatus.OPEN, due, None, now) is False


def test_is_breached_no_due_date_never_breaches():
    assert sla.is_breached(CaseStatus.OPEN, None, None) is False


def test_is_breached_resolved_before_due_is_not_breached():
    due = datetime(2026, 1, 1, tzinfo=UTC)
    resolved = due - timedelta(hours=2)
    assert sla.is_breached(CaseStatus.RESOLVED, due, resolved) is False


def test_is_breached_resolved_after_due_is_breached():
    due = datetime(2026, 1, 1, tzinfo=UTC)
    resolved = due + timedelta(hours=2)
    assert sla.is_breached(CaseStatus.RESOLVED, due, resolved) is True


def test_is_breached_ignores_current_time_once_resolved():
    """A resolved-on-time case must never flip to breached just because 'now' moved on."""
    due = datetime(2026, 1, 1, tzinfo=UTC)
    resolved = due - timedelta(hours=1)
    far_future = due + timedelta(days=365)
    assert sla.is_breached(CaseStatus.RESOLVED, due, resolved, far_future) is False


def test_hours_overdue_zero_when_not_due_yet():
    due = datetime(2026, 1, 1, tzinfo=UTC)
    now = due - timedelta(hours=5)
    assert sla.hours_overdue(due, now) == 0.0


def test_hours_overdue_positive_when_late():
    due = datetime(2026, 1, 1, tzinfo=UTC)
    now = due + timedelta(hours=10)
    assert sla.hours_overdue(due, now) == 10.0


def test_attainment_rate_no_resolutions_defaults_to_full():
    assert sla.attainment_rate(0, 0) == 100.0


def test_attainment_rate_partial():
    assert sla.attainment_rate(total_resolved=4, resolved_within_sla=3) == 75.0
