from datetime import date, timedelta


def create_document(client, headers, document_type, sample_entity, **overrides):
    payload = {
        "document_type_id": document_type.id,
        "entity_id": sample_entity.id,
        "issue_date": date.today().isoformat(),
        "provided_fields": {"signature": True, "tin": True},
    }
    payload.update(overrides)
    resp = client.post("/api/documents", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_document_full_completeness(
    client, analyst_headers, document_type, sample_entity, workflows
):
    doc = create_document(client, analyst_headers, document_type, sample_entity)
    assert doc["completeness_score"] == 100
    assert doc["missing_fields"] == []
    assert doc["review_status"] == "draft"


def test_create_document_incomplete_flags_missing_fields(
    client, analyst_headers, document_type, sample_entity, workflows
):
    doc = create_document(
        client, analyst_headers, document_type, sample_entity, provided_fields={"signature": True}
    )
    assert doc["completeness_score"] == 50
    assert doc["missing_fields"] == ["tin"]


def test_duplicate_detection_same_entity_type_issue_date(
    client, analyst_headers, document_type, sample_entity, workflows
):
    issue_date = date.today().isoformat()
    first = create_document(
        client, analyst_headers, document_type, sample_entity, issue_date=issue_date
    )
    second = create_document(
        client, analyst_headers, document_type, sample_entity, issue_date=issue_date
    )
    assert second["is_duplicate_of_id"] == first["id"]
    assert second["checksum"] == first["checksum"]


def test_submit_requires_full_completeness(
    client, analyst_headers, document_type, sample_entity, workflows
):
    doc = create_document(
        client, analyst_headers, document_type, sample_entity, provided_fields={"signature": True}
    )
    resp = client.post(f"/api/documents/{doc['id']}/submit", headers=analyst_headers)
    assert resp.status_code == 400


def test_document_approval_flow(
    client, analyst_headers, reviewer_headers, document_type, sample_entity, workflows
):
    doc = create_document(client, analyst_headers, document_type, sample_entity)
    submitted = client.post(f"/api/documents/{doc['id']}/submit", headers=analyst_headers)
    assert submitted.status_code == 200
    assert submitted.json()["review_status"] == "pending_review"

    forbidden = client.post(
        f"/api/documents/{doc['id']}/approve",
        headers=analyst_headers,
        json={"version": submitted.json()["version"]},
    )
    assert forbidden.status_code == 403

    approved = client.post(
        f"/api/documents/{doc['id']}/approve",
        headers=reviewer_headers,
        json={"version": submitted.json()["version"], "comment": "Looks good"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["review_status"] == "approved"


def test_document_rejection_flow(
    client, analyst_headers, reviewer_headers, document_type, sample_entity, workflows
):
    doc = create_document(client, analyst_headers, document_type, sample_entity)
    submitted = client.post(f"/api/documents/{doc['id']}/submit", headers=analyst_headers)
    rejected = client.post(
        f"/api/documents/{doc['id']}/reject",
        headers=reviewer_headers,
        json={"version": submitted.json()["version"], "reason": "Signature illegible"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["review_status"] == "rejected"


def test_document_optimistic_lock_on_approve(
    client, analyst_headers, reviewer_headers, document_type, sample_entity, workflows
):
    doc = create_document(client, analyst_headers, document_type, sample_entity)
    submitted = client.post(f"/api/documents/{doc['id']}/submit", headers=analyst_headers)
    stale_version = submitted.json()["version"] - 1
    resp = client.post(
        f"/api/documents/{doc['id']}/approve",
        headers=reviewer_headers,
        json={"version": stale_version},
    )
    assert resp.status_code == 409


def test_renew_document_creates_new_version(
    client, analyst_headers, document_type, sample_entity, workflows
):
    original = create_document(client, analyst_headers, document_type, sample_entity)
    renewed_resp = client.post(
        f"/api/documents/{original['id']}/renew",
        headers=analyst_headers,
        json={
            "document_type_id": document_type.id,
            "entity_id": sample_entity.id,
            "issue_date": date.today().isoformat(),
            "expiry_date": (date.today() + timedelta(days=1095)).isoformat(),
            "provided_fields": {"signature": True, "tin": True},
        },
    )
    assert renewed_resp.status_code == 201
    renewed = renewed_resp.json()
    assert renewed["id"] != original["id"]
    assert renewed["version_number"] == original["version_number"] + 1


def test_documents_expiring_filter(
    client, analyst_headers, document_type, sample_entity, workflows
):
    create_document(
        client,
        analyst_headers,
        document_type,
        sample_entity,
        expiry_date=(date.today() + timedelta(days=5)).isoformat(),
    )
    create_document(
        client,
        analyst_headers,
        document_type,
        sample_entity,
        issue_date=(date.today() - timedelta(days=100)).isoformat(),
        expiry_date=(date.today() + timedelta(days=500)).isoformat(),
    )
    resp = client.get(
        "/api/documents", headers=analyst_headers, params={"expiring_within_days": 30}
    )
    assert resp.json()["total"] == 1


def test_documents_expiring_filter_excludes_already_expired(
    client, analyst_headers, document_type, sample_entity, workflows
):
    """Matches the dashboard's expiring_within_window metric, which also excludes
    already-expired documents — the list filter must agree or dashboard tiles
    and their drill-down list disagree on the count."""
    create_document(
        client,
        analyst_headers,
        document_type,
        sample_entity,
        issue_date=(date.today() - timedelta(days=2000)).isoformat(),
        expiry_date=(date.today() - timedelta(days=10)).isoformat(),
    )
    resp = client.get(
        "/api/documents", headers=analyst_headers, params={"expiring_within_days": 30}
    )
    assert resp.json()["total"] == 0


def test_documents_csv_export(client, analyst_headers, document_type, sample_entity, workflows):
    create_document(client, analyst_headers, document_type, sample_entity)
    resp = client.get("/api/documents/export.csv", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
