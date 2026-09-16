def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_login_and_me(client, admin_headers):
    resp = client.get("/api/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_commit_inside_request_is_isolated_by_savepoint(client, admin_headers, db):
    from app.models.user import User

    resp = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "email": "new@controlflow.test.demo",
            "full_name": "New User",
            "password": "Password123!",
            "role": "reviewer",
        },
    )
    assert resp.status_code == 201, resp.text
    assert db.query(User).filter(User.email == "new@controlflow.test.demo").count() == 1
