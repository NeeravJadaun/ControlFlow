"""Idempotent daily/monthly monitoring jobs.

Each entry point takes an explicit `run_key` (defaults to "today"/"this
month") and immediately tries to INSERT a `JobRun` row under a DB unique
constraint on (job_name, run_key). If that insert fails because the row
already exists, the job has already run for that key and returns immediately
— this is what makes retries and duplicate Celery deliveries safe.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import logger, new_correlation_id
from app.db.session import SessionLocal
from app.models.audit import EscalationRule, JobRun
from app.models.case import Case, CaseQueue
from app.models.control import Control
from app.models.document import Document
from app.models.enums import (
    ClassificationStatus,
    ControlFrequency,
    ReviewStatus,
)
from app.models.financial import Classification
from app.services import escalation
from app.services.audit_log import record_audit
from app.services.classification import documentation_status
from app.tasks.celery_app import celery_app


def _start_job(db: Session, job_name: str, run_key: str) -> JobRun | None:
    """Returns the new JobRun row, or None if this (job_name, run_key) already ran."""
    job = JobRun(job_name=job_name, run_key=run_key, status="running", started_at=datetime.now(UTC))
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None
    return job


def _finish_job(db: Session, job: JobRun, summary: dict) -> None:
    job.status = "completed"
    job.finished_at = datetime.now(UTC)
    job.result_summary = summary
    db.commit()


def _expire_documents(db: Session, today: date, correlation_id: str) -> int:
    stale = (
        db.query(Document)
        .filter(Document.expiry_date.is_not(None), Document.expiry_date < today)
        .filter(Document.review_status != ReviewStatus.EXPIRED)
        .all()
    )
    for doc in stale:
        before = {"review_status": doc.review_status.value}
        doc.review_status = ReviewStatus.EXPIRED
        record_audit(
            db,
            actor_id=None,
            entity_type="document",
            entity_id=doc.id,
            action="auto_expire",
            before=before,
            after={"review_status": doc.review_status.value},
            correlation_id=correlation_id,
        )
    return len(stale)


def _refresh_case_sla_flags(db: Session, correlation_id: str) -> int:
    from app.models.enums import CaseStatus
    from app.services import sla

    now = datetime.now(UTC)
    open_statuses = [
        CaseStatus.OPEN,
        CaseStatus.IN_PROGRESS,
        CaseStatus.PENDING_REVIEW,
        CaseStatus.ESCALATED,
    ]
    cases = db.query(Case).filter(Case.status.in_(open_statuses), Case.due_at.is_not(None)).all()
    flagged = 0
    for c in cases:
        breached = sla.is_breached(c.status, c.due_at, c.resolved_at, now)
        if breached and not c.sla_breached:
            c.sla_breached = True
            flagged += 1
    return flagged


def _run_escalations(db: Session, correlation_id: str) -> int:
    from app.models.enums import CaseStatus

    rules = db.query(EscalationRule).filter(EscalationRule.is_active.is_(True)).all()
    if not rules:
        return 0
    open_statuses = [CaseStatus.OPEN, CaseStatus.IN_PROGRESS, CaseStatus.PENDING_REVIEW]
    cases = db.query(Case).filter(Case.status.in_(open_statuses), Case.due_at.is_not(None)).all()
    escalated = 0
    for c in cases:
        for rule in rules:
            if escalation.should_escalate(c, rule):
                escalation.apply_escalation(db, c, rule, correlation_id)
                escalated += 1
                break
    return escalated


def _refresh_classifications(db: Session, today: date, correlation_id: str) -> dict:
    classifications = db.query(Classification).all()
    updated = 0
    review_due_cases_created = 0
    queue = db.query(CaseQueue).filter(CaseQueue.key == "compliance-monitoring").first()
    for cl in classifications:
        has_docs = cl.status not in (
            ClassificationStatus.NOT_STARTED,
            ClassificationStatus.PENDING_DOCUMENTATION,
        )
        new_status = documentation_status(
            cl.classification_value or "", has_docs, cl.review_due_date, today
        )
        if new_status != cl.status:
            before = {"status": cl.status.value}
            cl.status = new_status
            updated += 1
            record_audit(
                db,
                actor_id=None,
                entity_type="classification",
                entity_id=cl.id,
                action="auto_status_update",
                before=before,
                after={"status": new_status.value},
                correlation_id=correlation_id,
            )
            if (
                new_status in (ClassificationStatus.REVIEW_DUE, ClassificationStatus.EXPIRED)
                and queue
            ):
                existing_open = (
                    db.query(Case)
                    .filter(
                        Case.entity_id == cl.entity_id,
                        Case.case_type == "classification_review",
                        Case.status.notin_(["resolved", "closed"]),
                    )
                    .first()
                )
                if not existing_open:
                    db.add(
                        Case(
                            queue_id=queue.id,
                            entity_id=cl.entity_id,
                            title=f"{cl.regime.value} classification review due",
                            description=(
                                f"Classification '{cl.classification_value}' status is now "
                                f"{new_status.value} and requires review."
                            ),
                            case_type="classification_review",
                            due_at=datetime.now(UTC) + timedelta(hours=queue.default_sla_hours),
                        )
                    )
                    review_due_cases_created += 1
    return {"classifications_updated": updated, "review_cases_created": review_due_cases_created}


@celery_app.task(name="app.tasks.monitoring.run_daily_monitoring")
def run_daily_monitoring(run_key: str | None = None) -> dict:
    run_key = run_key or date.today().isoformat()
    correlation_id = new_correlation_id()
    db = SessionLocal()
    try:
        job = _start_job(db, "daily_monitoring", run_key)
        if job is None:
            logger.info("daily_monitoring already ran for %s, skipping", run_key)
            return {"skipped": True, "run_key": run_key}

        today = date.fromisoformat(run_key)
        expired = _expire_documents(db, today, correlation_id)
        sla_flagged = _refresh_case_sla_flags(db, correlation_id)
        escalated = _run_escalations(db, correlation_id)
        classification_summary = _refresh_classifications(db, today, correlation_id)

        summary = {
            "documents_expired": expired,
            "cases_sla_flagged": sla_flagged,
            "cases_escalated": escalated,
            **classification_summary,
        }
        _finish_job(db, job, summary)
        logger.info("daily_monitoring completed: %s", summary)
        return summary
    finally:
        db.close()


@celery_app.task(name="app.tasks.monitoring.run_monthly_review")
def run_monthly_review(run_key: str | None = None) -> dict:
    run_key = run_key or date.today().strftime("%Y-%m")
    db = SessionLocal()
    try:
        job = _start_job(db, "monthly_review", run_key)
        if job is None:
            logger.info("monthly_review already ran for %s, skipping", run_key)
            return {"skipped": True, "run_key": run_key}

        controls = (
            db.query(Control)
            .filter(Control.frequency == ControlFrequency.MONTHLY, Control.is_active.is_(True))
            .all()
        )
        year, month = (int(p) for p in run_key.split("-"))
        month_start = date(year, month, 1)

        queue = db.query(CaseQueue).filter(CaseQueue.key == "control-testing").first()
        created = 0
        for control in controls:
            has_test_this_month = any(t.test_date >= month_start for t in control.tests)
            if not has_test_this_month and queue:
                db.add(
                    Case(
                        queue_id=queue.id,
                        title=f"Monthly control test due: {control.name}",
                        description=control.procedure or "",
                        case_type="control_testing",
                        due_at=datetime.now(UTC) + timedelta(hours=queue.default_sla_hours),
                    )
                )
                created += 1

        summary = {"monthly_controls_checked": len(controls), "test_cases_created": created}
        _finish_job(db, job, summary)
        logger.info("monthly_review completed: %s", summary)
        return summary
    finally:
        db.close()
