"""Integration tests for the idempotent daily/monthly monitoring jobs.

The Celery tasks open their own DB session via `app.tasks.monitoring.SessionLocal`.
To keep them inside the test's rolled-back transaction, we monkeypatch that
sessionmaker to bind to the same connection (via savepoints) rather than the
real engine.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def patch_task_session(db, monkeypatch):
    TestSessionLocal = sessionmaker(
        bind=db.get_bind(), join_transaction_mode="create_savepoint", future=True
    )
    monkeypatch.setattr("app.tasks.monitoring.SessionLocal", TestSessionLocal)
    return TestSessionLocal


def _run_daily(run_key=None):
    from app.tasks.monitoring import run_daily_monitoring

    return run_daily_monitoring.__wrapped__(run_key)


def _run_monthly(run_key=None):
    from app.tasks.monitoring import run_monthly_review

    return run_monthly_review.__wrapped__(run_key)


def test_daily_monitoring_is_idempotent(db, patch_task_session, workflows):
    run_key = date.today().isoformat()
    first = _run_daily(run_key)
    assert first.get("skipped") is not True

    second = _run_daily(run_key)
    assert second == {"skipped": True, "run_key": run_key}


def test_daily_monitoring_expires_stale_documents(
    db, patch_task_session, workflows, document_type, sample_entity
):
    from app.models.document import Document
    from app.models.enums import ReviewStatus

    expired_doc = Document(
        document_type_id=document_type.id,
        entity_id=sample_entity.id,
        issue_date=date.today() - timedelta(days=2000),
        expiry_date=date.today() - timedelta(days=10),
        review_status=ReviewStatus.APPROVED,
        completeness_score=100,
    )
    db.add(expired_doc)
    db.flush()

    result = _run_daily(date.today().isoformat())
    assert result["documents_expired"] == 1

    db.refresh(expired_doc)
    assert expired_doc.review_status == ReviewStatus.EXPIRED


def test_daily_monitoring_escalates_overdue_cases(db, patch_task_session, workflows, case_queue):
    from app.models.audit import EscalationRule
    from app.models.case import Case
    from app.models.enums import CaseStatus, WorkflowEntityType
    from app.services.workflow_engine import initiate

    db.add(
        EscalationRule(
            key="overdue-24h", applies_to="case", overdue_hours_threshold=24, action="escalate"
        )
    )
    case = Case(
        queue_id=case_queue.id,
        title="Overdue case",
        status=CaseStatus.OPEN,
        due_at=datetime.now(UTC) - timedelta(hours=48),
    )
    db.add(case)
    db.flush()
    initiate(db, workflows["case-lifecycle"], WorkflowEntityType.CASE, case.id)
    db.flush()

    result = _run_daily(date.today().isoformat())
    assert result["cases_escalated"] == 1

    db.refresh(case)
    assert case.status == CaseStatus.ESCALATED
    assert case.escalation_level == 1


def test_monthly_review_is_idempotent(db, patch_task_session, workflows, case_queue):
    from app.models.control import Control
    from app.models.enums import ControlFrequency

    db.add(
        Control(
            key="monthly-control",
            name="Monthly Control",
            frequency=ControlFrequency.MONTHLY,
            is_active=True,
        )
    )
    from app.models.case import CaseQueue

    db.add(CaseQueue(key="control-testing", name="Control Testing", default_sla_hours=120))
    db.flush()

    run_key = date.today().strftime("%Y-%m")
    first = _run_monthly(run_key)
    assert first["monthly_controls_checked"] == 1
    assert first["test_cases_created"] == 1

    second = _run_monthly(run_key)
    assert second == {"skipped": True, "run_key": run_key}
