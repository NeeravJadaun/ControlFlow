from datetime import date


def make_control(db):
    from app.models.control import Control
    from app.models.enums import ControlFrequency

    control = Control(
        key="test-control",
        name="Test Control",
        frequency=ControlFrequency.MONTHLY,
        procedure="Sample test procedure",
        evidence_requirement="Evidence link",
    )
    db.add(control)
    db.flush()
    return control


def test_record_control_test_requires_reviewer_role(client, analyst_headers, db):
    control = make_control(db)
    resp = client.post(
        "/api/controls/tests",
        headers=analyst_headers,
        json={"control_id": control.id, "test_date": date.today().isoformat(), "result": "pass"},
    )
    assert resp.status_code == 403


def test_record_and_list_control_tests(client, reviewer_headers, db):
    control = make_control(db)
    created = client.post(
        "/api/controls/tests",
        headers=reviewer_headers,
        json={
            "control_id": control.id,
            "test_date": date.today().isoformat(),
            "result": "fail",
            "notes": "Exception found",
            "evidence_ref": "evidence/1.txt",
        },
    )
    assert created.status_code == 201, created.text

    listed = client.get(f"/api/controls/{control.id}/tests", headers=reviewer_headers)
    assert len(listed.json()) == 1
    assert listed.json()[0]["result"] == "fail"


def test_sign_off_control_test(client, reviewer_headers, compliance_headers, db):
    control = make_control(db)
    test = client.post(
        "/api/controls/tests",
        headers=reviewer_headers,
        json={"control_id": control.id, "test_date": date.today().isoformat(), "result": "pass"},
    ).json()

    forbidden = client.post(f"/api/controls/tests/{test['id']}/sign-off", headers=reviewer_headers)
    assert forbidden.status_code == 403

    signed = client.post(f"/api/controls/tests/{test['id']}/sign-off", headers=compliance_headers)
    assert signed.status_code == 200
    assert signed.json()["signed_off_by_id"] is not None

    double_signoff = client.post(
        f"/api/controls/tests/{test['id']}/sign-off", headers=compliance_headers
    )
    assert double_signoff.status_code == 400


def test_remediation_task_lifecycle(client, reviewer_headers, analyst_headers, db):
    control = make_control(db)
    test = client.post(
        "/api/controls/tests",
        headers=reviewer_headers,
        json={"control_id": control.id, "test_date": date.today().isoformat(), "result": "fail"},
    ).json()

    task = client.post(
        "/api/controls/remediation-tasks",
        headers=analyst_headers,
        json={
            "control_test_id": test["id"],
            "description": "Fix the gap",
            "due_date": date.today().isoformat(),
        },
    )
    assert task.status_code == 201
    task_id = task.json()["id"]

    updated = client.patch(
        f"/api/controls/remediation-tasks/{task_id}",
        headers=analyst_headers,
        json={"status": "resolved"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "resolved"
    assert updated.json()["resolved_at"] is not None


def test_evidence_export_requires_auditor_or_compliance(
    client, analyst_headers, auditor_headers, reviewer_headers, db
):
    control = make_control(db)
    client.post(
        "/api/controls/tests",
        headers=reviewer_headers,
        json={"control_id": control.id, "test_date": date.today().isoformat(), "result": "pass"},
    )

    forbidden = client.get("/api/controls/evidence/export.csv", headers=analyst_headers)
    assert forbidden.status_code == 403

    allowed = client.get("/api/controls/evidence/export.csv", headers=auditor_headers)
    assert allowed.status_code == 200
    assert "test-control" in allowed.text
