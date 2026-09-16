def test_entity_update_writes_audit_log_with_before_after(client, admin_headers, record_type):
    entity_resp = client.post(
        "/api/entities",
        headers=admin_headers,
        json={"record_type_id": record_type.id, "kind": "client", "name": "Original Name"},
    )
    assert entity_resp.status_code == 201
    entity = entity_resp.json()

    update_resp = client.patch(
        f"/api/entities/{entity['id']}",
        headers=admin_headers,
        json={"name": "Updated Name", "version": entity["version"]},
    )
    assert update_resp.status_code == 200

    trail = client.get(f"/api/audit/entity/entity/{entity['id']}", headers=admin_headers)
    assert trail.status_code == 200
    actions = [row["action"] for row in trail.json()]
    assert actions == ["create", "update"]
    update_row = trail.json()[1]
    assert update_row["before"]["name"] == "Original Name"
    assert update_row["after"]["name"] == "Updated Name"


def test_audit_log_records_actor_and_correlation_id(client, admin_headers, record_type):
    resp = client.post(
        "/api/entities",
        headers=admin_headers,
        json={"record_type_id": record_type.id, "kind": "dealer", "name": "Some Dealer"},
    )
    entity_id = resp.json()["id"]

    trail = client.get(f"/api/audit/entity/entity/{entity_id}", headers=admin_headers)
    row = trail.json()[0]
    assert row["actor_id"] is not None
    assert row["correlation_id"] is not None
    assert row["entity_type"] == "entity"
    assert row["entity_id"] == entity_id


def test_audit_log_filterable_by_entity_type(client, admin_headers, auditor_headers, record_type):
    client.post(
        "/api/entities",
        headers=admin_headers,
        json={"record_type_id": record_type.id, "kind": "client", "name": "Filter Target"},
    )
    resp = client.get("/api/audit", headers=auditor_headers, params={"entity_type": "entity"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
    assert all(row["entity_type"] == "entity" for row in resp.json()["items"])
