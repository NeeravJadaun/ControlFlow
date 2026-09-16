def create_case(client, headers, case_queue, **overrides):
    payload = {"queue_id": case_queue.id, "title": "Test case", "priority": "medium"}
    payload.update(overrides)
    resp = client.post("/api/cases", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_and_get_case(client, analyst_headers, case_queue, workflows):
    case = create_case(client, analyst_headers, case_queue)
    assert case["status"] == "open"
    assert case["version"] == 1

    resp = client.get(f"/api/cases/{case['id']}", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Test case"


def test_case_lifecycle_start_resolve(client, analyst_headers, case_queue, workflows):
    case = create_case(client, analyst_headers, case_queue)

    resp = client.post(f"/api/cases/{case['id']}/start", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    resp = client.post(
        f"/api/cases/{case['id']}/resolve",
        headers=analyst_headers,
        json={
            "resolution_evidence": "Confirmed with client via call.",
            "version": resp.json()["version"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None


def test_case_resolve_requires_resolution_evidence_field(
    client, analyst_headers, case_queue, workflows
):
    case = create_case(client, analyst_headers, case_queue)
    client.post(f"/api/cases/{case['id']}/start", headers=analyst_headers)

    resp = client.post(
        f"/api/cases/{case['id']}/resolve",
        headers=analyst_headers,
        json={"resolution_evidence": "", "version": 2},
    )
    # empty string is rejected by CaseResolve's min_length=1 schema validation
    assert resp.status_code == 422


def test_case_close_requires_compliance_officer_role(
    client, analyst_headers, compliance_headers, case_queue, workflows
):
    case = create_case(client, analyst_headers, case_queue)
    client.post(f"/api/cases/{case['id']}/start", headers=analyst_headers)
    resolve = client.post(
        f"/api/cases/{case['id']}/resolve",
        headers=analyst_headers,
        json={"resolution_evidence": "Done.", "version": 2},
    )
    assert resolve.status_code == 200

    forbidden = client.post(f"/api/cases/{case['id']}/close", headers=analyst_headers)
    assert forbidden.status_code == 403

    allowed = client.post(f"/api/cases/{case['id']}/close", headers=compliance_headers)
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "closed"


def test_case_escalate_flow(client, analyst_headers, case_queue, workflows):
    case = create_case(client, analyst_headers, case_queue)
    resp = client.post(f"/api/cases/{case['id']}/escalate", headers=analyst_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "escalated"
    assert body["escalation_level"] == 1
    assert body["priority"] in ("high", "critical")


def test_optimistic_locking_rejects_stale_version(client, analyst_headers, case_queue, workflows):
    case = create_case(client, analyst_headers, case_queue)
    resp = client.patch(
        f"/api/cases/{case['id']}",
        headers=analyst_headers,
        json={"title": "Updated title", "version": case["version"]},
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 2

    stale = client.patch(
        f"/api/cases/{case['id']}",
        headers=analyst_headers,
        json={"title": "Conflicting update", "version": case["version"]},
    )
    assert stale.status_code == 409


def test_case_comments(client, analyst_headers, case_queue, workflows):
    case = create_case(client, analyst_headers, case_queue)
    resp = client.post(
        f"/api/cases/{case['id']}/comments", headers=analyst_headers, json={"body": "Following up."}
    )
    assert resp.status_code == 201
    listed = client.get(f"/api/cases/{case['id']}/comments", headers=analyst_headers)
    assert len(listed.json()) == 1


def test_case_attachments(client, analyst_headers, case_queue, workflows):
    case = create_case(client, analyst_headers, case_queue)
    resp = client.post(
        f"/api/cases/{case['id']}/attachments",
        headers=analyst_headers,
        json={"filename": "evidence.txt", "content_type": "text/plain", "size_bytes": 128},
    )
    assert resp.status_code == 201
    listed = client.get(f"/api/cases/{case['id']}/attachments", headers=analyst_headers)
    assert len(listed.json()) == 1
    assert listed.json()[0]["filename"] == "evidence.txt"


def test_bulk_update_cases(client, analyst_headers, case_queue, workflows):
    c1 = create_case(client, analyst_headers, case_queue)
    c2 = create_case(client, analyst_headers, case_queue)
    resp = client.post(
        "/api/cases/bulk-update",
        headers=analyst_headers,
        json={"case_ids": [c1["id"], c2["id"]], "priority": "high"},
    )
    assert resp.status_code == 200
    assert all(c["priority"] == "high" for c in resp.json())


def test_cases_csv_export(client, analyst_headers, case_queue, workflows):
    create_case(client, analyst_headers, case_queue)
    resp = client.get("/api/cases/export.csv", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "Test case" in resp.text


def test_cases_csv_import(client, analyst_headers, case_queue, workflows):
    csv_content = f"queue_key,title,priority\n{case_queue.key},Imported Case,high\n"
    resp = client.post(
        "/api/cases/import",
        headers=analyst_headers,
        files={"file": ("cases.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert body["errors"] == []

    listing = client.get("/api/cases", headers=analyst_headers, params={"q": "Imported Case"})
    assert listing.json()["total"] == 1


def test_cases_csv_import_reports_row_errors(client, analyst_headers, workflows):
    csv_content = "queue_key,title,priority\nnonexistent-queue,Bad Row,high\n"
    resp = client.post(
        "/api/cases/import",
        headers=analyst_headers,
        files={"file": ("cases.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 0
    assert len(body["errors"]) == 1


def test_case_search_and_filter(client, analyst_headers, case_queue, workflows):
    create_case(client, analyst_headers, case_queue, title="Alpha renewal review")
    create_case(client, analyst_headers, case_queue, title="Beta control test")

    resp = client.get("/api/cases", headers=analyst_headers, params={"q": "Alpha"})
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "Alpha renewal review"


def test_open_only_filter_matches_dashboard_open_scope(
    client, analyst_headers, case_queue, workflows, db
):
    """The open_only list filter must select exactly the statuses the dashboard's
    open/overdue/by-priority metrics count, or a tile's drilldown link shows a
    different total than the number on the tile."""
    open_case = create_case(client, analyst_headers, case_queue)
    client.post(f"/api/cases/{open_case['id']}/start", headers=analyst_headers)
    resolved_case = create_case(client, analyst_headers, case_queue)
    client.post(f"/api/cases/{resolved_case['id']}/start", headers=analyst_headers)
    client.post(
        f"/api/cases/{resolved_case['id']}/resolve",
        headers=analyst_headers,
        json={"resolution_evidence": "Done.", "version": 2},
    )

    resp = client.get("/api/cases", headers=analyst_headers, params={"open_only": True})
    ids = {c["id"] for c in resp.json()["items"]}
    assert open_case["id"] in ids
    assert resolved_case["id"] not in ids


def test_saved_views(client, analyst_headers):
    resp = client.post(
        "/api/cases/views/saved",
        headers=analyst_headers,
        json={"name": "My overdue cases", "entity_type": "case", "filters": {"overdue_only": True}},
    )
    assert resp.status_code == 201
    listed = client.get("/api/cases/views/saved", headers=analyst_headers)
    assert len(listed.json()) == 1
    assert listed.json()[0]["name"] == "My overdue cases"
