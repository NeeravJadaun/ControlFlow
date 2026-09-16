# Demo Guide

## Getting in

```bash
make demo
```

brings up Postgres, Redis, runs migrations, seeds deterministic demo data,
and starts the API, worker, beat, and frontend. Then open
**http://localhost:5173**.

## Demo credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@controlflow.demo | Admin123! |
| Compliance Officer | compliance.officer@controlflow.demo | Compliance123! |
| Reviewer | reviewer@controlflow.demo | Reviewer123! |
| Auditor | auditor@controlflow.demo | Auditor123! |
| Operations Analyst | analyst@controlflow.demo | Analyst123! |

The login page lists these too — click a row to autofill.

## Deterministic dataset

Seeding uses a fixed RNG seed (`DEMO_SEED=20240101`), so every fresh
`make seed-reset` produces **exactly** the same 300 entities, 500 accounts,
372 contacts, 1,025 documents, 250 cases, 40 controls, 100 control tests, 323
classifications, and 300 distributions — including the same record IDs
referenced below. If you've clicked around and want the scenarios back to
their starting state, run:

```bash
make seed-reset
```

Seeding writes a summary, including the scenario IDs below, to
`sample_data/demo_scenarios.json`.

## Scenario 1 — Document approval

1. Log in as **Operations Analyst**.
2. Go to **Documents** → open document **#986** (a KYC onboarding pack,
   100% complete, sitting in `pending_review`).
3. Notice there's no "Approve" button — the analyst role can't approve.
4. Sign out, log back in as **Reviewer**.
5. Open document #986 again → click **Approve**. Status flips to `approved`,
   and the audit trail shows the `approve` action with your user as actor.

To see the *creation* half of this flow: **Documents → New document**, pick
any entity ID (e.g. `34`) and document type, check all required fields, and
submit — completeness reaches 100% and a **Submit for review** button
appears.

## Scenario 2 — Document renewal reminder

1. Go to **Documents**, filter "Any expiry window" → **Expiring in 7 days**.
2. Document **#916** is in that list — its expiry is inside the 7-day
   window, which is exactly the bucket the daily monitoring job checks.
3. Open Document Detail to see its expiry date and completeness.

Document **#1001** is a seeded duplicate (same entity, document type, and
issue date as an earlier document) — open it to see the "possible duplicate
of #…" banner, demonstrating duplicate detection.

## Scenario 3 — Case resolution

1. Log in as **Operations Analyst**, open **Case #5** ("Classification
   Review"), currently `in_progress`.
2. Click **Resolve**, enter resolution evidence, confirm.
3. Status becomes `resolved`, the workflow-state row matches, and the audit
   trail shows the `resolve` action with before/after JSON.

## Scenario 4 — Overdue escalation

1. From the **Dashboard**, click the **Overdue cases** tile — it drills down
   into `/cases?overdue_only=true`, the same live-computed set the tile
   counted.
2. Open **Case #17** (flagged overdue in the seed) or any case showing a red
   "failed" SLA badge.
3. Click **Escalate**. Status becomes `escalated`, escalation level
   increments, priority is bumped to at least High, and a system comment is
   added.
4. Case **#23** already shows this end-state pre-seeded (escalation level 1,
   an auto-escalation comment) so you can see the *result* without waiting
   for the daily job.

## Scenario 5 — Control testing

1. Log in as **Reviewer**, go to **Controls & Testing**, click any control
   in the list (e.g. "Document Completeness Review").
2. Fill in **Record control test**: pick a date, set result to **Fail**, add
   a note, click **Record test**. It appears at the top of Test History.
3. Sign out, log in as **Compliance Officer**, open the same control, click
   **Sign off** next to the new test.
4. Switch to the **Remediation Tasks** tab to see any open tasks from failed
   tests; mark one resolved to see the status update.

## Scenario 6 — Audit-package export

1. Log in as **Auditor**.
2. **Controls & Testing → Export audit evidence** downloads
   `audit_evidence.csv`: one row per control test with control key/name,
   date, result, sample/evidence references, and sign-off actor/timestamp.
3. Visit **Audit Log** to browse the full immutable log, filterable by
   entity type. Try logging in as an Operations Analyst and visiting the
   same page — access is denied (Auditor/Compliance Officer only).

## Scenario 7 — Daily and monthly monitoring (background jobs)

These run automatically on a schedule (`beat`: daily at 02:00 UTC, monthly on
the 1st at 03:00 UTC) but you can trigger them immediately to see the
effect without waiting:

```bash
docker compose exec worker python -c "
from app.tasks.monitoring import run_daily_monitoring, run_monthly_review
print(run_daily_monitoring())
print(run_monthly_review())
"
```

The first call on any given day/month does real work (expires past-due
documents, refreshes case SLA-breach flags, runs escalation rules, updates
classification statuses, opens monthly control-test cases where one is
missing) and returns a summary dict. Run the exact same command again — you
get `{"skipped": true, "run_key": "..."}` back immediately, because the
`(job_name, run_key)` unique constraint on `job_runs` makes the job
idempotent. This idempotency is also covered by an automated test
(`backend/tests/integration/test_monitoring_jobs.py`).

## Financial-operations workspace

**Financial Ops Workspace** in the sidebar has two tabs:

- **FATCA / CRS / QI Classifications** — entity **#34** has a classification
  in `review_due` status (the seed intentionally biases one entity into this
  state so the scenario is always reproducible).
- **Fund Fact Sheets & Maturity Notices** — distributions in `pending`,
  `sent`, and `acknowledged` states; click **Mark sent** / **Acknowledge** on
  a pending/sent row to walk the distribution lifecycle.

Every page in this workspace carries a banner: *"Educational and simplified
only... not legal, tax, or regulatory advice."* This is not decorative — see
`docs/security-and-limitations.md`.

## Running the automated demo verification

```bash
make test   # backend (pytest, 80%+ coverage gate) + frontend build
make lint   # black/ruff/mypy + frontend lint
make e2e    # Playwright, against a running `make up` stack
```
