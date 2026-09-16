# Test Plan

## Summary (as last verified in this environment)

| Suite | Count | Result |
|---|---|---|
| Backend unit tests | 44 | passing |
| Backend integration tests | 90 | passing |
| Backend domain-logic coverage | — | **93.1%** (`pytest --cov=app`), floor enforced at 80% in CI |
| Playwright e2e tests | 10 | passing |
| Frontend build / type-check | — | passing (`tsc -b && vite build`) |
| Frontend lint (oxlint) | — | passing (2 informational warnings, 0 errors) |
| Backend format/lint/type-check | — | black, ruff, mypy all clean |

Run `make test` (backend + frontend) or `make e2e` (Playwright, needs `make
up` running first) to reproduce.

## Strategy

Three layers, matching the pyramid:

1. **Unit tests** (`backend/tests/unit/`) — pure functions with no DB or HTTP:
   SLA math, renewal/completeness/duplicate-detection logic, FATCA/CRS/QI
   classification rules, escalation decision logic. These run in
   milliseconds and need no fixtures beyond plain Python objects.
2. **Integration tests** (`backend/tests/integration/`) — real Postgres
   (`controlflow_test`, auto-created), real FastAPI app via
   `TestClient`, real Alembic migrations. No mocks. Each test runs inside a
   SAVEPOINT-backed transaction that's rolled back afterward, so `db.commit()`
   calls inside route handlers behave normally but nothing leaks between
   tests (`backend/tests/conftest.py`).
3. **End-to-end tests** (`tests/e2e/`) — Playwright against the real running
   frontend + backend + Postgres + Redis, driving the browser exactly as a
   user would.

### Why real Postgres instead of SQLite or mocks

The schema uses Postgres-specific types (`JSONB`, `ARRAY`) and the
optimistic-locking tests rely on real transaction semantics. A prior version
of this plan considered SQLite for speed; it was rejected because it would
have silently skipped exactly the kind of bug this project actually hit
(see below).

## What the integration suite covers

- **Database migrations**: `test_migrations.py` runs `alembic upgrade head`
  against a throwaway database from empty, then a full
  downgrade/upgrade round-trip, asserting the expected tables appear and
  disappear.
- **APIs**: full CRUD + state-transition coverage for cases, documents,
  entities, controls, and the financial workspace, including error paths
  (404s, 403s, 409 optimistic-lock conflicts, 400 validation failures).
- **Authorization**: unauthenticated/invalid-token rejection, wrong-password
  rejection, inactive-user rejection, and role-gated endpoints (user
  creation, audit log access, document approval, control sign-off, evidence
  export) tested both for the forbidden and allowed role.
- **Background jobs**: `test_monitoring_jobs.py` monkey-patches the Celery
  task's `SessionLocal` to bind to the *same* test transaction (via
  `join_transaction_mode="create_savepoint"`), then calls the task functions
  directly. Verifies: documents past expiry flip to `expired`; overdue cases
  get escalated; a second call with the same `run_key` is a no-op
  (idempotency, checked via the `job_runs` unique constraint).
- **Idempotency**: covered both as an integration test (above) and manually
  by running the same job twice in a live environment and diffing the
  result (`{"skipped": true, ...}` on the second call).
- **Audit history**: `test_audit_log.py` asserts a create+update sequence
  produces exactly the expected `AuditLog` rows with correct before/after
  JSON, actor, and correlation ID.
- **Imports/exports**: CSV import for cases and entities (including
  per-row error reporting for bad data) and CSV export for cases, documents,
  entities, and control-test evidence.
- **Dashboard/drilldown consistency**: every dashboard metric has a test
  that also hits the list endpoint with the matching filter and asserts the
  counts agree — this is the category of bug described below, and it's now
  a regression test, not just a one-time fix.

## Bugs this test process actually found (not hypothetical)

Writing the tests — especially the Playwright suite and the browser-driven
manual pass that preceded it — surfaced seven real bugs, all fixed and now
covered by a regression test:

1. **Renewal-urgency bucket order was backwards**
   (`services/renewal.py::REMINDER_THRESHOLDS_DAYS`): thresholds were
   `(90, 60, 30, 7)`, and the loop returned on the *first* match, so a
   document expiring in 5 days was bucketed as "due in 90" instead of "due
   in 7". Caught by `tests/unit/test_renewal.py::test_renewal_urgency_buckets`
   before it ever reached a browser. Fixed by reversing the tuple.
2. **Seed data set case/document status columns without driving the
   workflow engine**, so the engine's derived "current state" disagreed with
   the actual status — the UI showed the wrong action buttons (e.g. "Start
   work" on an already-resolved case), and calling `approve` on a
   seeded pending-review document failed with "No transition 'approve' from
   state 'draft'". Caught by manually walking the case-resolution and
   document-approval demo scenarios in a real browser. Fixed by having the
   seed script write a realistic `WorkflowEvent` path for every non-initial
   status (see `docs/workflow-design.md`).
3. **`initiate()` always timestamped `occurred_at=now()`**, so even after
   fix #2, a backdated seeded case's later "start" event could end up
   chronologically *before* its "create" event (since "create" was stamped
   with the real wall-clock seed-run time). `current_state_key()` orders by
   `occurred_at DESC`, so it picked the wrong event. Fixed by adding an
   `occurred_at` parameter to `initiate()` and passing the entity's real
   backdated timestamp from the seed script.
4. **`overdue_only` case-list filter used the batch-computed `sla_breached`
   flag**, which is only refreshed by the daily job, while the dashboard's
   "Overdue cases" tile computed overdue live from `due_at`. A case overdue
   since the last seed/reset wouldn't show as overdue in the list until the
   job next ran, even though the dashboard already counted it. Caught by a
   Playwright test asserting the tile's number matches the drilldown list's
   total. Fixed by making the list filter compute live, matching the
   dashboard.
5. **"Open cases" and "Critical priority cases" tiles linked to
   unfiltered/partially-filtered case-list URLs**, so their drilldown totals
   didn't match the tile numbers (the tiles are scoped to open-ish
   statuses; the links weren't). Fixed by adding an `open_only` list filter
   (shared `OPEN_STATUSES` constant in `services/sla.py`, used by both the
   dashboard query and the list filter) and updating the tile links.
6. **Documents list's `expiring_within_days` filter had no lower bound**, so
   it included already-*expired* documents, while the dashboard's
   `expiring_within_window` metric explicitly excludes them. Fixed by adding
   the matching `expiry_date >= today` bound to the list filter.
7. **CSV export buttons were plain `<a href> target="_blank">` links.**
   These endpoints require a JWT bearer token, which a browser never attaches
   to a plain navigation — every export was silently returning 401 with
   nothing downloaded. Caught by a Playwright test waiting on a `download`
   event that never fired. Fixed by fetching the file as an authenticated
   blob (`api/client.ts::downloadFile`) and triggering the save via a
   throwaway object URL, for all four export buttons (cases, documents,
   entities, control evidence).

The throughline: **every one of these was a live-verification catch, not a
code-review catch.** Static review of the seed script or the dashboard
links would very plausibly have missed all seven — they only became visible
by actually logging in, clicking through the demo scenarios, and asserting
that numbers/states shown in one place matched another.

## End-to-end scenarios (`tests/e2e/specs/`)

| Spec | Scenario |
|---|---|
| `case-resolution.spec.ts` | Analyst starts and resolves a case; status, workflow state, and audit trail all update consistently |
| `document-approval.spec.ts` | Analyst creates + submits a document; reviewer approves it; completeness gating and role gating both exercised |
| `overdue-escalation.spec.ts` | An overdue case is escalated from its detail page; dashboard "Overdue" tile drills down into the same set |
| `control-testing.spec.ts` | Reviewer records a failing control test; compliance officer signs it off |
| `dashboard-filtering.spec.ts` | Dashboard tiles (critical cases, expiring documents) and the cases-page filter dropdown drill down into matching, correctly-filtered lists |
| `audit-package-export.spec.ts` | Auditor downloads the control-evidence CSV; role gating on the full audit log; auditor can browse it |

E2E tests create some of their own data via direct API calls (fast, avoids
depending on specific seeded IDs) and interact with the rest through the UI.
Because they mutate real data, re-run `make seed-reset` before a clean
demo/screenshot session.

## Coverage configuration

`backend/pyproject.toml`: `fail_under = 80`, source scoped to `app/`,
`app/main.py` and `app/seed/*` excluded (wiring and data generation, not
domain logic). Current measured coverage is 93.1%; the lowest-covered
modules are `tasks/monitoring.py` (91%, the untested lines are the
`__main__`-style Celery task registration boilerplate) and
`services/dashboards.py` (93%, a few rarely-hit trend-query branches).
