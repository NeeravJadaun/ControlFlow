from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services import dashboards as dash

router = APIRouter()


@router.get("/cases/open-overdue")
def cases_open_overdue(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> dict:
    return dash.open_and_overdue_cases(db)


@router.get("/cases/sla-attainment")
def cases_sla_attainment(
    since: date | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    return dash.sla_attainment(db, since)


@router.get("/cases/sla-trend")
def cases_sla_trend(
    days: int = Query(180, ge=1, le=730),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[dict]:
    return dash.sla_attainment_trend(db, days)


@router.get("/cases/monthly-trend")
def cases_monthly_trend(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[dict]:
    return dash.monthly_case_trend(db, months)


@router.get("/cases/workload-by-owner")
def cases_workload_by_owner(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[dict]:
    return dash.workload_by_owner(db)


@router.get("/documents/expiring")
def documents_expiring(
    within_days: int = Query(90, ge=1, le=3650),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    return dash.expiring_documents(db, within_days)


@router.get("/controls/pass-rate")
def controls_pass_rate(
    since: date | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    return dash.control_pass_rate(db, since)


@router.get("/controls/exception-aging")
def controls_exception_aging(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> dict:
    return dash.exception_aging(db)


@router.get("/controls/remediation-status")
def controls_remediation_status(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> dict:
    return dash.remediation_status(db)


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> dict:
    """One call for the landing dashboard: every headline metric at once."""
    return {
        "cases": dash.open_and_overdue_cases(db),
        "sla": dash.sla_attainment(db),
        "documents": dash.expiring_documents(db),
        "controls": dash.control_pass_rate(db),
        "remediation": dash.remediation_status(db),
        "exception_aging": dash.exception_aging(db),
        "workload": dash.workload_by_owner(db),
    }
