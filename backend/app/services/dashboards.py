"""SQL-backed dashboard metrics. Every metric returns enough structure for the
frontend to drill down into a filtered list view (status/date-range/owner).
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import case as sql_case
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.control import Control, ControlTest, RemediationTask
from app.models.document import Document
from app.models.enums import CaseStatus, ControlResult, RemediationStatus
from app.models.user import User
from app.services import renewal
from app.services.sla import OPEN_STATUSES


def open_and_overdue_cases(db: Session) -> dict:
    now = datetime.now(UTC)
    open_statuses = OPEN_STATUSES
    total_open = db.execute(
        select(func.count()).select_from(Case).where(Case.status.in_(open_statuses))
    ).scalar_one()
    overdue = db.execute(
        select(func.count())
        .select_from(Case)
        .where(Case.status.in_(open_statuses), Case.due_at.is_not(None), Case.due_at < now)
    ).scalar_one()
    by_priority = db.execute(
        select(Case.priority, func.count())
        .where(Case.status.in_(open_statuses))
        .group_by(Case.priority)
    ).all()
    return {
        "open": total_open,
        "overdue": overdue,
        "by_priority": {p.value: c for p, c in by_priority},
    }


def sla_attainment(db: Session, since: date | None = None) -> dict:
    stmt = select(
        func.count().label("total"),
        func.sum(sql_case((Case.sla_breached.is_(False), 1), else_=0)).label("within_sla"),
    ).where(Case.status.in_([CaseStatus.RESOLVED, CaseStatus.CLOSED]))
    if since:
        stmt = stmt.where(Case.resolved_at >= since)
    row = db.execute(stmt).one()
    total, within = row.total or 0, row.within_sla or 0
    rate = 100.0 if total == 0 else round((within / total) * 100, 2)
    return {"total_resolved": total, "resolved_within_sla": within, "attainment_rate": rate}


def sla_attainment_trend(db: Session, days: int = 180) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=days)
    day_col = func.date_trunc("day", Case.resolved_at).label("day")
    stmt = (
        select(
            day_col,
            func.count().label("total"),
            func.sum(sql_case((Case.sla_breached.is_(False), 1), else_=0)).label("within_sla"),
        )
        .where(
            Case.status.in_([CaseStatus.RESOLVED, CaseStatus.CLOSED]),
            Case.resolved_at.is_not(None),
            Case.resolved_at >= since,
        )
        .group_by(day_col)
        .order_by(day_col)
    )
    rows = db.execute(stmt).all()
    return [
        {
            "date": r.day.date().isoformat(),
            "total": r.total,
            "within_sla": r.within_sla,
            "attainment_rate": 100.0 if r.total == 0 else round((r.within_sla / r.total) * 100, 2),
        }
        for r in rows
    ]


def expiring_documents(db: Session, within_days: int = 90) -> dict:
    today = datetime.now(UTC).date()
    horizon = today + timedelta(days=within_days)
    stmt = (
        select(func.count())
        .select_from(Document)
        .where(
            Document.expiry_date.is_not(None),
            Document.expiry_date >= today,
            Document.expiry_date <= horizon,
        )
    )
    expiring = db.execute(stmt).scalar_one()
    expired = db.execute(
        select(func.count())
        .select_from(Document)
        .where(Document.expiry_date.is_not(None), Document.expiry_date < today)
    ).scalar_one()
    by_type = db.execute(
        select(Document.document_type_id, func.count())
        .where(
            Document.expiry_date.is_not(None),
            Document.expiry_date >= today,
            Document.expiry_date <= horizon,
        )
        .group_by(Document.document_type_id)
    ).all()

    all_expiry_dates = (
        db.execute(select(Document.expiry_date).where(Document.expiry_date.is_not(None)))
        .scalars()
        .all()
    )
    renewal_buckets: dict[str, int] = {}
    for expiry_date in all_expiry_dates:
        bucket = renewal.renewal_urgency(expiry_date, today).value
        renewal_buckets[bucket] = renewal_buckets.get(bucket, 0) + 1

    return {
        "expiring_within_window": expiring,
        "expired": expired,
        "renewal_buckets": renewal_buckets,
        "window_days": within_days,
        "by_document_type_id": {t: c for t, c in by_type},
    }


def exception_aging(db: Session) -> dict:
    today = date.today()
    buckets = {"0_7": 0, "8_30": 0, "31_60": 0, "60_plus": 0}
    rows = db.execute(
        select(RemediationTask.due_date).where(RemediationTask.status != RemediationStatus.RESOLVED)
    ).all()
    for (due_date,) in rows:
        if due_date is None:
            continue
        age = (today - due_date).days
        if age <= 7:
            buckets["0_7"] += 1
        elif age <= 30:
            buckets["8_30"] += 1
        elif age <= 60:
            buckets["31_60"] += 1
        else:
            buckets["60_plus"] += 1
    return buckets


def control_pass_rate(db: Session, since: date | None = None) -> dict:
    stmt = select(
        func.count().label("total"),
        func.sum(sql_case((ControlTest.result == ControlResult.PASS, 1), else_=0)).label("passed"),
    )
    if since:
        stmt = stmt.where(ControlTest.test_date >= since)
    row = db.execute(stmt).one()
    total, passed = row.total or 0, row.passed or 0
    rate = 100.0 if total == 0 else round((passed / total) * 100, 2)

    by_control = db.execute(
        select(
            Control.key,
            Control.name,
            func.count().label("total"),
            func.sum(sql_case((ControlTest.result == ControlResult.PASS, 1), else_=0)).label(
                "passed"
            ),
        )
        .join(ControlTest, ControlTest.control_id == Control.id)
        .group_by(Control.key, Control.name)
    ).all()
    return {
        "total_tests": total,
        "passed": passed,
        "pass_rate": rate,
        "by_control": [
            {
                "key": r.key,
                "name": r.name,
                "total": r.total,
                "passed": r.passed,
                "pass_rate": 100.0 if r.total == 0 else round((r.passed / r.total) * 100, 2),
            }
            for r in by_control
        ],
    }


def remediation_status(db: Session) -> dict:
    rows = db.execute(
        select(RemediationTask.status, func.count()).group_by(RemediationTask.status)
    ).all()
    return {status.value: count for status, count in rows}


def workload_by_owner(db: Session) -> list[dict]:
    open_statuses = OPEN_STATUSES
    rows = db.execute(
        select(User.id, User.full_name, func.count(Case.id))
        .join(Case, Case.owner_id == User.id)
        .where(Case.status.in_(open_statuses))
        .group_by(User.id, User.full_name)
        .order_by(func.count(Case.id).desc())
    ).all()
    return [{"owner_id": uid, "owner_name": name, "open_cases": count} for uid, name, count in rows]


def monthly_case_trend(db: Session, months: int = 6) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=30 * months)
    month_col = func.date_trunc("month", Case.created_at).label("month")
    created = db.execute(
        select(month_col, func.count())
        .where(Case.created_at >= since)
        .group_by(month_col)
        .order_by(month_col)
    ).all()
    resolved_month_col = func.date_trunc("month", Case.resolved_at).label("month")
    resolved = db.execute(
        select(resolved_month_col, func.count())
        .where(Case.resolved_at.is_not(None), Case.resolved_at >= since)
        .group_by(resolved_month_col)
        .order_by(resolved_month_col)
    ).all()
    resolved_map = {m.date().isoformat(): c for m, c in resolved}
    return [
        {
            "month": m.date().isoformat(),
            "created": c,
            "resolved": resolved_map.get(m.date().isoformat(), 0),
        }
        for m, c in created
    ]
