import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_correlation_id, get_current_user, get_db, require_roles
from app.models.control import Control, ControlTest, RemediationTask
from app.models.enums import Role
from app.models.user import User
from app.schemas.control import (
    ControlOut,
    ControlTestCreate,
    ControlTestOut,
    RemediationTaskCreate,
    RemediationTaskOut,
    RemediationTaskUpdate,
)
from app.services.audit_log import record_audit

router = APIRouter()


@router.get("", response_model=list[ControlOut])
def list_controls(
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Control]:
    stmt = select(Control)
    if is_active is not None:
        stmt = stmt.where(Control.is_active == is_active)
    return list(db.execute(stmt.order_by(Control.key)).scalars().all())


@router.get("/{control_id}", response_model=ControlOut)
def get_control(
    control_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> Control:
    control = db.get(Control, control_id)
    if control is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Control not found")
    return control


@router.get("/{control_id}/tests", response_model=list[ControlTestOut])
def list_control_tests(
    control_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
) -> list[ControlTest]:
    return list(
        db.execute(
            select(ControlTest)
            .where(ControlTest.control_id == control_id)
            .order_by(ControlTest.test_date.desc())
        )
        .scalars()
        .all()
    )


@router.post("/tests", response_model=ControlTestOut, status_code=status.HTTP_201_CREATED)
def record_control_test(
    payload: ControlTestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.REVIEWER, Role.COMPLIANCE_OFFICER, Role.AUDITOR)),
    correlation_id: str = Depends(get_correlation_id),
) -> ControlTest:
    control = db.get(Control, payload.control_id)
    if control is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Control not found")
    test = ControlTest(
        control_id=payload.control_id,
        tester_id=user.id,
        reviewer_id=control.reviewer_id,
        sample_ref=payload.sample_ref,
        test_date=payload.test_date,
        result=payload.result,
        notes=payload.notes,
        evidence_ref=payload.evidence_ref,
    )
    db.add(test)
    db.flush()
    record_audit(
        db,
        actor_id=user.id,
        entity_type="control_test",
        entity_id=test.id,
        action="create",
        after={"control_id": control.id, "result": payload.result.value},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(test)
    return test


@router.post("/tests/{test_id}/sign-off", response_model=ControlTestOut)
def sign_off_test(
    test_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.COMPLIANCE_OFFICER, Role.AUDITOR)),
    correlation_id: str = Depends(get_correlation_id),
) -> ControlTest:
    test = db.get(ControlTest, test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Control test not found")
    if test.signed_off_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Test is already signed off")
    test.signed_off_by_id = user.id
    test.signed_off_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=user.id,
        entity_type="control_test",
        entity_id=test.id,
        action="sign_off",
        after={"signed_off_by_id": user.id},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(test)
    return test


@router.get("/remediation-tasks", response_model=list[RemediationTaskOut])
def list_remediation_tasks(
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[RemediationTask]:
    stmt = select(RemediationTask)
    if status_filter:
        stmt = stmt.where(RemediationTask.status == status_filter)
    return list(db.execute(stmt.order_by(RemediationTask.due_date)).scalars().all())


@router.post(
    "/remediation-tasks", response_model=RemediationTaskOut, status_code=status.HTTP_201_CREATED
)
def create_remediation_task(
    payload: RemediationTaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> RemediationTask:
    test = db.get(ControlTest, payload.control_test_id)
    if test is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Control test not found")
    task = RemediationTask(
        control_test_id=payload.control_test_id,
        description=payload.description,
        owner_id=payload.owner_id,
        due_date=payload.due_date,
    )
    db.add(task)
    db.flush()
    record_audit(
        db,
        actor_id=user.id,
        entity_type="remediation_task",
        entity_id=task.id,
        action="create",
        after={"control_test_id": test.id},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(task)
    return task


@router.patch("/remediation-tasks/{task_id}", response_model=RemediationTaskOut)
def update_remediation_task(
    task_id: int,
    payload: RemediationTaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
) -> RemediationTask:
    task = db.get(RemediationTask, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Remediation task not found")
    before = {"status": task.status.value}
    task.status = payload.status
    if payload.status.value == "resolved":
        task.resolved_at = datetime.now(UTC)
    record_audit(
        db,
        actor_id=user.id,
        entity_type="remediation_task",
        entity_id=task.id,
        action="status_update",
        before=before,
        after={"status": task.status.value},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(task)
    return task


@router.get("/evidence/export.csv")
def export_evidence_csv(
    db: Session = Depends(get_db),
    _user: User = Depends(require_roles(Role.AUDITOR, Role.COMPLIANCE_OFFICER)),
) -> StreamingResponse:
    """Audit-package export: every control test with result, evidence ref, and sign-off."""
    rows = db.execute(
        select(ControlTest, Control)
        .join(Control, ControlTest.control_id == Control.id)
        .order_by(ControlTest.test_date)
    ).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "control_key",
            "control_name",
            "test_date",
            "result",
            "sample_ref",
            "evidence_ref",
            "tester_id",
            "signed_off_by_id",
            "signed_off_at",
        ]
    )
    for test, control in rows:
        writer.writerow(
            [
                control.key,
                control.name,
                test.test_date,
                test.result.value,
                test.sample_ref,
                test.evidence_ref,
                test.tester_id,
                test.signed_off_by_id,
                test.signed_off_at,
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_evidence.csv"},
    )
