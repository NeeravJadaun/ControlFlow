def test_unauthenticated_request_rejected(client):
    resp = client.get("/api/cases")
    assert resp.status_code == 401


def test_invalid_token_rejected(client):
    resp = client.get("/api/cases", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_wrong_password_rejected(client, admin_user):
    resp = client.post(
        "/api/auth/login", json={"email": admin_user.email, "password": "WrongPassword!"}
    )
    assert resp.status_code == 401


def test_non_admin_cannot_create_user(client, analyst_headers):
    resp = client.post(
        "/api/users",
        headers=analyst_headers,
        json={
            "email": "someone@controlflow.test.demo",
            "full_name": "Someone",
            "password": "Password123!",
            "role": "reviewer",
        },
    )
    assert resp.status_code == 403


def test_admin_can_create_user(client, admin_headers):
    resp = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "email": "newperson@controlflow.test.demo",
            "full_name": "New Person",
            "password": "Password123!",
            "role": "reviewer",
        },
    )
    assert resp.status_code == 201


def test_only_auditor_or_compliance_can_list_audit_log(
    client, analyst_headers, auditor_headers, compliance_headers
):
    forbidden = client.get("/api/audit", headers=analyst_headers)
    assert forbidden.status_code == 403

    for headers in (auditor_headers, compliance_headers):
        allowed = client.get("/api/audit", headers=headers)
        assert allowed.status_code == 200


def test_inactive_user_cannot_authenticate(client, db):
    from app.core.security import hash_password
    from app.models.enums import Role
    from app.models.user import User

    user = User(
        email="inactive@controlflow.test.demo",
        full_name="Inactive User",
        hashed_password=hash_password("Password123!"),
        role=Role.OPERATIONS_ANALYST,
        is_active=False,
    )
    db.add(user)
    db.flush()

    resp = client.post("/api/auth/login", json={"email": user.email, "password": "Password123!"})
    assert resp.status_code == 401
