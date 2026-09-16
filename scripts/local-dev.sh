#!/usr/bin/env bash
# Bootstrap ControlFlow against local Postgres/Redis instead of Docker.
# Useful when Docker itself is unavailable. See docs/runbook.md.
#
# Prerequisites: Postgres 16+ and Redis running locally, Python 3.12, Node 22.
# Usage: scripts/local-dev.sh [--reset]

set -euo pipefail
cd "$(dirname "$0")/.."

PG_USER=controlflow
PG_DB=controlflow
PG_PASSWORD=controlflow

echo "==> Ensuring local Postgres role and database exist"
psql postgres -tc "SELECT 1 FROM pg_roles WHERE rolname = '${PG_USER}'" | grep -q 1 \
  || psql postgres -c "CREATE ROLE ${PG_USER} WITH LOGIN SUPERUSER PASSWORD '${PG_PASSWORD}';"
psql postgres -tc "SELECT 1 FROM pg_database WHERE datname = '${PG_DB}'" | grep -q 1 \
  || psql postgres -c "CREATE DATABASE ${PG_DB} OWNER ${PG_USER};"

export DATABASE_URL="postgresql+psycopg://${PG_USER}:${PG_PASSWORD}@localhost:5432/${PG_DB}"
export REDIS_URL="redis://localhost:6379/0"
export SECRET_KEY="local-dev-secret-not-for-production-use-only-synthetic-data"

echo "==> Installing backend dependencies"
cd backend
if [ ! -d .venv ]; then python3.12 -m venv .venv; fi
source .venv/bin/activate
pip install -q -r requirements-dev.txt

echo "==> Running migrations"
alembic upgrade head

echo "==> Seeding demo data"
if [ "${1:-}" = "--reset" ]; then
  python -m app.seed.seed --reset
else
  python -m app.seed.seed
fi

cd ../frontend
echo "==> Installing frontend dependencies"
npm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local

cat <<'EOF'

==> Setup complete. Start the app in two terminals:

  (backend)  cd backend  && source .venv/bin/activate && \
             DATABASE_URL="postgresql+psycopg://controlflow:controlflow@localhost:5432/controlflow" \
             REDIS_URL="redis://localhost:6379/0" \
             uvicorn app.main:app --reload

  (frontend) cd frontend && npm run dev

Frontend: http://localhost:5173
API docs: http://localhost:8000/docs
EOF
