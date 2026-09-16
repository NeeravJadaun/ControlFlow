def test_list_case_queues(client, analyst_headers, case_queue):
    resp = client.get("/api/cases/queues", headers=analyst_headers)
    assert resp.status_code == 200
    assert any(q["key"] == case_queue.key for q in resp.json())


def test_list_document_types(client, analyst_headers, document_type):
    resp = client.get("/api/documents/types", headers=analyst_headers)
    assert resp.status_code == 200
    assert any(t["key"] == document_type.key for t in resp.json())


def test_list_record_types(client, analyst_headers, record_type):
    resp = client.get("/api/entities/record-types", headers=analyst_headers)
    assert resp.status_code == 200
    assert any(rt["key"] == record_type.key for rt in resp.json())
