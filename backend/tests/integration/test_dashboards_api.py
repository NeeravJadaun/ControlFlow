from datetime import UTC, datetime, timedelta


def make_resolved_case(db, case_queue, breached: bool):
    from app.models.case import Case
    from app.models.enums import CaseStatus

    due = datetime.now(UTC) - timedelta(days=1)
    resolved_at = due + timedelta(hours=5) if breached else due - timedelta(hours=5)
    case = Case(
        queue_id=case_queue.id,
        title="Dashboard case",
        status=CaseStatus.RESOLVED,
        due_at=due,
        resolved_at=resolved_at,
        sla_breached=breached,
    )
    db.add(case)
    db.flush()
    return case


def test_open_and_overdue_cases_endpoint(client, analyst_headers, db, case_queue):
    from app.models.case import Case
    from app.models.enums import CaseStatus

    db.add(
        Case(
            queue_id=case_queue.id,
            title="Overdue",
            status=CaseStatus.OPEN,
            due_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    db.add(
        Case(
            queue_id=case_queue.id,
            title="On time",
            status=CaseStatus.OPEN,
            due_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.flush()

    resp = client.get("/api/dashboards/cases/open-overdue", headers=analyst_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["open"] == 2
    assert body["overdue"] == 1


def test_sla_attainment_endpoint(client, analyst_headers, db, case_queue):
    make_resolved_case(db, case_queue, breached=False)
    make_resolved_case(db, case_queue, breached=True)

    resp = client.get("/api/dashboards/cases/sla-attainment", headers=analyst_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_resolved"] == 2
    assert body["resolved_within_sla"] == 1
    assert body["attainment_rate"] == 50.0


def test_control_pass_rate_endpoint(client, analyst_headers, db):
    from datetime import date

    from app.models.control import Control, ControlTest
    from app.models.enums import ControlFrequency, ControlResult

    control = Control(
        key="dash-control", name="Dashboard Control", frequency=ControlFrequency.MONTHLY
    )
    db.add(control)
    db.flush()
    db.add(ControlTest(control_id=control.id, test_date=date.today(), result=ControlResult.PASS))
    db.add(ControlTest(control_id=control.id, test_date=date.today(), result=ControlResult.FAIL))
    db.flush()

    resp = client.get("/api/dashboards/controls/pass-rate", headers=analyst_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tests"] == 2
    assert body["pass_rate"] == 50.0


def test_dashboard_summary_endpoint_returns_all_sections(client, analyst_headers):
    resp = client.get("/api/dashboards/summary", headers=analyst_headers)
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "cases",
        "sla",
        "documents",
        "controls",
        "remediation",
        "exception_aging",
        "workload",
    ):
        assert key in body


def test_dashboard_drilldown_matches_list_filter(client, analyst_headers, db, case_queue):
    from app.models.case import Case
    from app.models.enums import CaseStatus

    db.add(
        Case(
            queue_id=case_queue.id,
            title="Overdue drilldown",
            status=CaseStatus.OPEN,
            due_at=datetime.now(UTC) - timedelta(hours=5),
        )
    )
    db.flush()

    summary = client.get("/api/dashboards/cases/open-overdue", headers=analyst_headers).json()
    drilldown = client.get("/api/cases", headers=analyst_headers, params={"overdue_only": True})
    assert drilldown.json()["total"] == summary["overdue"]
