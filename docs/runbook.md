# Runbook

## Prerequisites

- Docker + Docker Compose v2
- (Optional, for local non-Docker development) Python 3.12 and Node 22

## First-time setup

```bash
git clone <this-repo>
cd ControlFlow
cp .env.example .env
make demo        # up db+redis, migrate, seed, up api+worker+beat+frontend
```

Frontend: http://localhost:5173 · API + interactive docs: http://localhost:8000/docs

## Everyday commands

| Command | Effect |
|---|---|
| `docker compose up --build` | Start everything in the foreground |
| `make up` | Same, via Makefile |
| `make down` | Stop and remove containers |
| `make seed` | Seed demo data (no-op if already seeded) |
| `make seed-reset` | Truncate and reseed from scratch (deterministic) |
| `make migrate` | Run pending Alembic migrations |
| `make test` | Backend pytest (80% coverage gate) + frontend build |
| `make lint` | black/ruff/mypy (backend) + oxlint (frontend) |
| `make e2e` | Playwright, against a stack started with `make up` |
| `make logs` | Tail all service logs |

## Environment variables (`.env`, see `.env.example`)

| Variable | Purpose |
|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Postgres container credentials |
| `DATABASE_URL` | SQLAlchemy connection string used by the api/worker/beat/migrate services |
| `REDIS_URL` | Celery broker + result backend |
| `SECRET_KEY` | JWT signing key — **change for anything beyond local demo use** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime (default 480 = 8h) |
| `CORS_ORIGINS` | JSON list of allowed frontend origins |
| `DEMO_SEED` | RNG seed for deterministic data generation |
| `LOG_LEVEL` | Backend structured-log level |
| `VITE_API_BASE_URL` | Where the frontend points its API calls |

None of these ship with production-grade secrets — every default in
`.env.example` is explicitly a synthetic/demo value.

## Health checks

- `GET /health` — liveness, no dependencies checked.
- `GET /health/ready` — readiness, executes `SELECT 1` against Postgres.
- Postgres and Redis containers have their own `healthcheck` entries in
  `docker-compose.yml`; the `api`/`worker`/`beat` services wait on
  `migrate` completing successfully and on Redis being healthy before
  starting.

## Background jobs

Celery Beat schedules (`backend/app/tasks/celery_app.py`):

| Job | Schedule | What it does |
|---|---|---|
| `run_daily_monitoring` | 02:00 UTC daily | Expires past-due documents, refreshes case SLA-breach flags, runs escalation rules, refreshes classification statuses (opening a compliance-review case when one crosses into review-due/expired) |
| `run_monthly_review` | 03:00 UTC on the 1st | Opens a control-testing case for every active monthly control missing a test this month |

Both are **idempotent**: each run first tries to insert a `JobRun` row under
a unique `(job_name, run_key)` constraint (`run_key` defaults to today's date
/ this month). If the insert fails because that key already ran, the task
returns `{"skipped": true, "run_key": "..."}` immediately without touching
any data. Safe to trigger manually (see `docs/demo-guide.md`) or to have
Celery redeliver without side effects.

To watch a job run live:

```bash
docker compose logs -f worker
```

## Database migrations

```bash
# generate a new migration after changing models
docker compose exec api alembic revision --autogenerate -m "describe the change"

# apply
make migrate

# roll back one revision
docker compose exec api alembic downgrade -1
```

`backend/tests/integration/test_migrations.py` runs a full
empty→head→base→head round-trip against a throwaway database as part of the
normal test suite, so a broken migration fails CI, not just a manual check.

## Logging

Structured JSON logs (`app/core/logging.py`) on stdout, one line per request:
timestamp, level, logger name, correlation ID, HTTP method/path/status/
duration. A correlation ID is generated per request (or read from an
incoming `X-Correlation-Id` header), stored in a `ContextVar`, echoed back in
the response header, and threaded through to the matching `AuditLog.
correlation_id` — so a single user action can be traced from access log to
audit trail. No secrets, tokens, or raw personal data are ever logged; log
statements reference entity types/IDs and actions, not field values.

## Troubleshooting

**`docker compose up` fails to pull/build an image with an I/O or "blob
expected" error.** This is local Docker Desktop image-store corruption, not
a project issue. Try `docker system prune` (removes unused images/containers
— confirm this is acceptable first) or restart Docker Desktop. If Docker is
unusable, the backend can run directly against local Postgres/Redis (see
below) — everything in this repo was verified that way during development.

**Running without Docker** (useful if Docker itself is unavailable):

```bash
# Postgres + Redis via Homebrew, or any local install
brew services start postgresql@16
brew install redis && brew services start redis
createuser controlflow -s --pwprompt   # or via psql: CREATE ROLE ... LOGIN SUPERUSER PASSWORD ...
createdb controlflow -O controlflow

cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL="postgresql+psycopg://controlflow:controlflow@localhost:5432/controlflow"
export REDIS_URL="redis://localhost:6379/0"
alembic upgrade head
python -m app.seed.seed
uvicorn app.main:app --reload   # http://localhost:8000

cd ../frontend
npm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local
npm run dev   # http://localhost:5173
```

**`alembic upgrade head` fails with "relation already exists".** The
database has tables from a different migration history (e.g. you switched
branches). For a demo environment it's safe to drop and recreate the
database (`dropdb controlflow && createdb controlflow -O controlflow`, or
`docker compose down -v` to also drop the named volume) and re-run migrate +
seed — this is synthetic data, never anything worth preserving.

**Seed says "already contains seed data" but you want fresh data.** Use
`make seed-reset` (or `python -m app.seed.seed --reset`), which truncates
every seed-managed table (`RESTART IDENTITY CASCADE`) before regenerating.

**Playwright can't reach the app.** `make e2e` assumes a stack is already
running (`make up` or `make demo` first). Override `FRONTEND_URL` /
`API_URL` env vars if you're running the servers on non-default ports.
