.PHONY: up down build seed test test-backend test-frontend lint lint-backend lint-frontend e2e demo logs migrate

# Bring the full stack up (Postgres, Redis, API, worker, beat, frontend)
up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

# Run pending Alembic migrations inside the api container
migrate:
	docker compose run --rm migrate

# Seed deterministic synthetic demo data (safe to re-run; skips if already seeded)
seed:
	docker compose run --rm api python -m app.seed.seed

# Re-seed from scratch
seed-reset:
	docker compose run --rm api python -m app.seed.seed --reset

# Run backend + frontend automated test suites
test: test-backend test-frontend

test-backend:
	docker compose run --rm api pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=80

test-frontend:
	cd frontend && npm run build

# Format check, lint, and type-check both apps
lint: lint-backend lint-frontend

lint-backend:
	docker compose run --rm api sh -c "black --check app tests && ruff check app tests && mypy app"

lint-frontend:
	cd frontend && npm run lint

# Run the Playwright end-to-end suite against a running stack (`make up` first)
e2e:
	cd tests/e2e && npm install && npx playwright install --with-deps chromium && npx playwright test

# One-shot: bring the stack up, migrate, seed, and print demo credentials
demo:
	docker compose up --build -d db redis
	$(MAKE) migrate
	$(MAKE) seed
	docker compose up --build -d api worker beat frontend
	@echo ""
	@echo "ControlFlow is running:"
	@echo "  Frontend:  http://localhost:5173"
	@echo "  API docs:  http://localhost:8000/docs"
	@echo ""
	@echo "Demo credentials (see docs/demo-guide.md for full scenario walkthroughs):"
	@echo "  Admin               admin@controlflow.demo               Admin123!"
	@echo "  Compliance Officer  compliance.officer@controlflow.demo  Compliance123!"
	@echo "  Reviewer            reviewer@controlflow.demo            Reviewer123!"
	@echo "  Auditor             auditor@controlflow.demo             Auditor123!"
	@echo "  Operations Analyst  analyst@controlflow.demo             Analyst123!"

logs:
	docker compose logs -f
