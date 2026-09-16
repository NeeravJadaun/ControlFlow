def test_create_and_search_entities(client, admin_headers, record_type):
    resp = client.post(
        "/api/entities",
        headers=admin_headers,
        json={
            "record_type_id": record_type.id,
            "kind": "client",
            "name": "Northwind Traders",
            "jurisdiction": "US",
        },
    )
    assert resp.status_code == 201

    listed = client.get("/api/entities", headers=admin_headers, params={"q": "Northwind"})
    assert listed.json()["total"] == 1

    filtered_by_jurisdiction = client.get(
        "/api/entities", headers=admin_headers, params={"jurisdiction": "GB"}
    )
    assert filtered_by_jurisdiction.json()["total"] == 0


def test_entity_optimistic_locking(client, admin_headers, record_type):
    created = client.post(
        "/api/entities",
        headers=admin_headers,
        json={"record_type_id": record_type.id, "kind": "client", "name": "Original"},
    ).json()

    ok = client.patch(
        f"/api/entities/{created['id']}",
        headers=admin_headers,
        json={"status": "under_review", "version": created["version"]},
    )
    assert ok.status_code == 200

    stale = client.patch(
        f"/api/entities/{created['id']}",
        headers=admin_headers,
        json={"status": "active", "version": created["version"]},
    )
    assert stale.status_code == 409


def test_entities_csv_export(client, admin_headers, record_type):
    client.post(
        "/api/entities",
        headers=admin_headers,
        json={"record_type_id": record_type.id, "kind": "dealer", "name": "Acme Securities"},
    )
    resp = client.get("/api/entities/export.csv", headers=admin_headers)
    assert resp.status_code == 200
    assert "Acme Securities" in resp.text


def test_entities_csv_import(client, admin_headers, record_type):
    csv_content = (
        "kind,name,record_type_key,jurisdiction\n"
        f"client,Imported Client One,{record_type.key},US\n"
        f"client,Imported Client Two,{record_type.key},GB\n"
    )
    resp = client.post(
        "/api/entities/import",
        headers=admin_headers,
        files={"file": ("entities.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 2
    assert body["errors"] == []

    listed = client.get("/api/entities", headers=admin_headers, params={"q": "Imported"})
    assert listed.json()["total"] == 2


def test_entities_csv_import_rejects_unknown_record_type(client, admin_headers):
    csv_content = "kind,name,record_type_key\nclient,Bad Row,nonexistent\n"
    resp = client.post(
        "/api/entities/import",
        headers=admin_headers,
        files={"file": ("entities.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 0
    assert len(body["errors"]) == 1


def test_entity_accounts_and_contacts_listing(client, admin_headers, sample_entity, db):
    from app.models.entity import Account, Contact

    db.add(Account(entity_id=sample_entity.id, account_number="ACC-999", account_type="custody"))
    db.add(Contact(entity_id=sample_entity.id, name="Jane Doe", role="Relationship Manager"))
    db.flush()

    accounts = client.get(f"/api/entities/{sample_entity.id}/accounts", headers=admin_headers)
    assert len(accounts.json()) == 1

    contacts = client.get(f"/api/entities/{sample_entity.id}/contacts", headers=admin_headers)
    assert len(contacts.json()) == 1
