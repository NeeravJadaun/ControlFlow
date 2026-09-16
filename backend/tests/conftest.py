"""Shared pytest fixtures.

Tests run against a real Postgres database (`controlflow_test`, created
automatically if missing) rather than SQLite or mocks, because the app
relies on Postgres-specific types (JSONB, ARRAY) and behavior (optimistic
locking via version columns). Each test runs inside an outer transaction
that is rolled back afterward, using SQLAlchemy's savepoint-based join mode
so that `db.commit()` calls inside route/service code don't leak between
tests.
"""

from collections.abc import Generator

import psycopg
import pytest
from app.api.deps import get_db
from app.core.config import get_settings
from app.core.security import hash_password
from app.models import Base
from app.models.enums import Role
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

# Derived from DATABASE_URL rather than hardcoded to `localhost` so the same
# suite works unmodified whether pytest runs on the host (DATABASE_URL host
# is `localhost`) or inside the `api` container on the compose network
# (DATABASE_URL host is `db`) — see docs/runbook.md.
_APP_DB_URL = make_url(get_settings().database_url)
TEST_DB_NAME = "controlflow_test"
_TEST_DB_URL_OBJ = _APP_DB_URL.set(database=TEST_DB_NAME)
_MAINTENANCE_URL_OBJ = _APP_DB_URL.set(database="postgres").set(drivername="postgresql")

MAINTENANCE_DSN = _MAINTENANCE_URL_OBJ.render_as_string(hide_password=False)
TEST_DATABASE_URL = _TEST_DB_URL_OBJ.render_as_string(hide_password=False)


def _ensure_test_database() -> None:
    conn = psycopg.connect(MAINTENANCE_DSN, autocommit=True)
    try:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        conn.close()


@pytest.fixture(scope="session")
def test_engine():
    _ensure_test_database()
    engine = create_engine(TEST_DATABASE_URL, future=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(test_engine) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionForTest = sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", future=True
    )
    session = SessionForTest()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_user(db: Session, role: Role, email: str | None = None) -> User:
    email = email or f"{role.value}@controlflow.test.demo"
    user = User(
        email=email,
        full_name=f"Test {role.value.title()}",
        hashed_password=hash_password("TestPass123!"),
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def auth_headers(client: TestClient, email: str, password: str = "TestPass123!") -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user(db: Session) -> User:
    return make_user(db, Role.ADMIN, "admin@controlflow.test.demo")


@pytest.fixture
def admin_headers(client: TestClient, admin_user: User) -> dict:
    return auth_headers(client, admin_user.email)


@pytest.fixture
def analyst_user(db: Session) -> User:
    return make_user(db, Role.OPERATIONS_ANALYST, "analyst@controlflow.test.demo")


@pytest.fixture
def analyst_headers(client: TestClient, analyst_user: User) -> dict:
    return auth_headers(client, analyst_user.email)


@pytest.fixture
def reviewer_user(db: Session) -> User:
    return make_user(db, Role.REVIEWER, "reviewer@controlflow.test.demo")


@pytest.fixture
def reviewer_headers(client: TestClient, reviewer_user: User) -> dict:
    return auth_headers(client, reviewer_user.email)


@pytest.fixture
def compliance_officer_user(db: Session) -> User:
    return make_user(db, Role.COMPLIANCE_OFFICER, "compliance@controlflow.test.demo")


@pytest.fixture
def compliance_headers(client: TestClient, compliance_officer_user: User) -> dict:
    return auth_headers(client, compliance_officer_user.email)


@pytest.fixture
def auditor_user(db: Session) -> User:
    return make_user(db, Role.AUDITOR, "auditor@controlflow.test.demo")


@pytest.fixture
def auditor_headers(client: TestClient, auditor_user: User) -> dict:
    return auth_headers(client, auditor_user.email)


@pytest.fixture
def workflows(db: Session):
    from app.seed.seed import seed_workflows

    return seed_workflows(db)


@pytest.fixture
def case_queue(db: Session):
    from app.models.case import CaseQueue

    queue = CaseQueue(key="operations", name="Operations", default_sla_hours=48)
    db.add(queue)
    db.flush()
    return queue


@pytest.fixture
def document_type(db: Session):
    from app.models.document import DocumentType

    dt = DocumentType(
        key="w9",
        name="W-9",
        category="tax_form",
        required_fields=["signature", "tin"],
        expiry_applicable=True,
        renewal_period_days=1095,
    )
    db.add(dt)
    db.flush()
    return dt


@pytest.fixture
def record_type(db: Session):
    from app.models.entity import RecordType

    rt = RecordType(key="client", name="Client")
    db.add(rt)
    db.flush()
    return rt


@pytest.fixture
def sample_entity(db: Session, record_type):
    from app.models.entity import Entity
    from app.models.enums import EntityKind

    entity = Entity(
        record_type_id=record_type.id,
        kind=EntityKind.CLIENT,
        name="Acme Test Client",
        jurisdiction="US",
        attributes={"us_person": True, "entity_type": "individual"},
    )
    db.add(entity)
    db.flush()
    return entity
