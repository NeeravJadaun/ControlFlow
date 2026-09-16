from datetime import UTC, date, datetime, timedelta


def test_sla_trend_endpoint(client, analyst_headers, db, case_queue):
    from app.models.case import Case
    from app.models.enums import CaseStatus

    resolved_at = datetime.now(UTC) - timedelta(days=2)
    db.add(
        Case(
            queue_id=case_queue.id,
            title="Trend case",
            status=CaseStatus.RESOLVED,
            due_at=resolved_at + timedelta(hours=1),
            resolved_at=resolved_at,
            sla_breached=False,
        )
    )
    db.flush()

    resp = client.get(
        "/api/dashboards/cases/sla-trend", headers=analyst_headers, params={"days": 30}
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert any(row["total"] >= 1 for row in resp.json())


def test_monthly_trend_endpoint(client, analyst_headers, db, case_queue):
    from app.models.case import Case
    from app.models.enums import CaseStatus

    db.add(Case(queue_id=case_queue.id, title="Monthly trend case", status=CaseStatus.OPEN))
    db.flush()

    resp = client.get(
        "/api/dashboards/cases/monthly-trend", headers=analyst_headers, params={"months": 3}
    )
    assert resp.status_code == 200
    assert any(row["created"] >= 1 for row in resp.json())


def test_workload_by_owner_endpoint(client, analyst_headers, analyst_user, db, case_queue):
    from app.models.case import Case
    from app.models.enums import CaseStatus

    db.add(
        Case(
            queue_id=case_queue.id,
            title="Owned case",
            status=CaseStatus.OPEN,
            owner_id=analyst_user.id,
        )
    )
    db.flush()

    resp = client.get("/api/dashboards/cases/workload-by-owner", headers=analyst_headers)
    assert resp.status_code == 200
    assert any(row["owner_id"] == analyst_user.id and row["open_cases"] == 1 for row in resp.json())


def test_documents_expiring_endpoint_and_renewal_buckets(
    client, analyst_headers, db, document_type, sample_entity
):
    from app.models.document import Document
    from app.models.enums import ReviewStatus

    db.add(
        Document(
            document_type_id=document_type.id,
            entity_id=sample_entity.id,
            issue_date=date.today() - timedelta(days=1000),
            expiry_date=date.today() + timedelta(days=5),
            review_status=ReviewStatus.APPROVED,
            completeness_score=100,
        )
    )
    db.flush()

    resp = client.get(
        "/api/dashboards/documents/expiring", headers=analyst_headers, params={"within_days": 90}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["expiring_within_window"] == 1
    assert body["renewal_buckets"].get("due_7") == 1


def test_exception_aging_endpoint(client, analyst_headers, db):
    from app.models.control import Control, ControlTest, RemediationTask
    from app.models.enums import ControlFrequency, ControlResult, RemediationStatus

    control = Control(key="aging-control", name="Aging Control", frequency=ControlFrequency.MONTHLY)
    db.add(control)
    db.flush()
    test = ControlTest(control_id=control.id, test_date=date.today(), result=ControlResult.FAIL)
    db.add(test)
    db.flush()
    db.add(
        RemediationTask(
            control_test_id=test.id,
            description="Old exception",
            due_date=date.today() - timedelta(days=90),
            status=RemediationStatus.OPEN,
        )
    )
    db.flush()

    resp = client.get("/api/dashboards/controls/exception-aging", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["60_plus"] == 1


def test_remediation_status_endpoint(client, analyst_headers, db):
    from app.models.control import Control, ControlTest, RemediationTask
    from app.models.enums import ControlFrequency, ControlResult, RemediationStatus

    control = Control(
        key="remediation-status-control",
        name="Remediation Control",
        frequency=ControlFrequency.MONTHLY,
    )
    db.add(control)
    db.flush()
    test = ControlTest(control_id=control.id, test_date=date.today(), result=ControlResult.FAIL)
    db.add(test)
    db.flush()
    db.add(
        RemediationTask(
            control_test_id=test.id, description="Task", status=RemediationStatus.IN_PROGRESS
        )
    )
    db.flush()

    resp = client.get("/api/dashboards/controls/remediation-status", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json().get("in_progress") == 1


def test_control_pass_rate_by_control_breakdown(client, analyst_headers, db):
    from app.models.control import Control, ControlTest
    from app.models.enums import ControlFrequency, ControlResult

    control = Control(
        key="breakdown-control", name="Breakdown Control", frequency=ControlFrequency.MONTHLY
    )
    db.add(control)
    db.flush()
    db.add(ControlTest(control_id=control.id, test_date=date.today(), result=ControlResult.PASS))
    db.flush()

    resp = client.get("/api/dashboards/controls/pass-rate", headers=analyst_headers)
    assert resp.status_code == 200
    by_control = {row["key"]: row for row in resp.json()["by_control"]}
    assert by_control["breakdown-control"]["pass_rate"] == 100.0
