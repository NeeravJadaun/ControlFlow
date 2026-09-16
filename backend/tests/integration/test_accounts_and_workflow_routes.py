from app.models.entity import Account


def test_list_and_get_accounts(client, admin_headers, sample_entity, db):
    db.add(
        Account(
            entity_id=sample_entity.id,
            account_number="ACC-100",
            account_type="custody",
            status="open",
        )
    )
    db.add(
        Account(
            entity_id=sample_entity.id,
            account_number="ACC-101",
            account_type="brokerage",
            status="closed",
        )
    )
    db.flush()

    all_accounts = client.get("/api/accounts", headers=admin_headers)
    assert all_accounts.json()["total"] == 2

    open_only = client.get("/api/accounts", headers=admin_headers, params={"status": "open"})
    assert open_only.json()["total"] == 1

    by_entity = client.get(
        "/api/accounts", headers=admin_headers, params={"entity_id": sample_entity.id}
    )
    assert by_entity.json()["total"] == 2

    single = client.get(
        f"/api/accounts/{by_entity.json()['items'][0]['id']}", headers=admin_headers
    )
    assert single.status_code == 200


def test_get_account_404(client, admin_headers):
    resp = client.get("/api/accounts/999999", headers=admin_headers)
    assert resp.status_code == 404


def test_workflow_status_and_history_endpoints(client, analyst_headers, case_queue, workflows):
    case = client.post(
        "/api/cases",
        headers=analyst_headers,
        json={"queue_id": case_queue.id, "title": "Workflow test case"},
    ).json()

    status_resp = client.get(
        f"/api/workflows/case-lifecycle/case/{case['id']}", headers=analyst_headers
    )
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["current_state"] == "open"
    assert {t["key"] for t in body["available_transitions"]} >= {"start", "escalate"}

    history_resp = client.get(
        f"/api/workflows/case-lifecycle/case/{case['id']}/history", headers=analyst_headers
    )
    assert history_resp.status_code == 200
    assert len(history_resp.json()) == 1
    assert history_resp.json()[0]["to_state_key"] == "open"


def test_workflow_generic_transition_endpoint(client, analyst_headers, case_queue, workflows):
    case = client.post(
        "/api/cases",
        headers=analyst_headers,
        json={"queue_id": case_queue.id, "title": "Generic transition case"},
    ).json()

    resp = client.post(
        f"/api/workflows/case-lifecycle/case/{case['id']}/transitions",
        headers=analyst_headers,
        params={"transition_key": "start", "comment": "Kicking off"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["to_state_key"] == "in_progress"

    status_resp = client.get(
        f"/api/workflows/case-lifecycle/case/{case['id']}", headers=analyst_headers
    )
    assert status_resp.json()["current_state"] == "in_progress"


def test_workflow_transition_endpoint_rejects_invalid_transition(
    client, analyst_headers, case_queue, workflows
):
    case = client.post(
        "/api/cases",
        headers=analyst_headers,
        json={"queue_id": case_queue.id, "title": "Invalid transition case"},
    ).json()
    resp = client.post(
        f"/api/workflows/case-lifecycle/case/{case['id']}/transitions",
        headers=analyst_headers,
        params={"transition_key": "close"},
    )
    assert resp.status_code == 400


def test_workflow_status_unknown_workflow_key_404s(client, analyst_headers):
    resp = client.get("/api/workflows/does-not-exist/case/1", headers=analyst_headers)
    assert resp.status_code == 404
