# Requirements

ControlFlow is a configurable operations-and-compliance platform for regulated
teams that manage records, documents, cases, service deadlines, approvals,
control testing, escalations, and audit evidence. The core product is
industry-neutral; a financial-operations workspace is layered on top as a
concrete demo.

## Functional requirements

### Records and cases
- Configurable record types (`RecordType`), with owners, statuses, priorities,
  tags, and a JSONB `attributes` bag for type-specific fields.
- Case queues with per-queue default SLA hours; SLA due dates scale with
  priority (critical = 0.25x, high = 0.5x, medium = 1x, low = 2x the queue's
  base window).
- Case lifecycle: open → in_progress → pending_review → resolved → closed,
  with escalation from any open-ish state and reopen from escalated/resolved.
- Comments, attachment metadata, resolution evidence, and bulk status/priority
  updates across selected cases.
- Search by title, filter by status/priority/owner/entity/queue, CSV
  import/export, and per-user saved views (name + filter JSON).

### Document controls
- Document types define required fields, whether expiry applies, and the
  renewal period. Completeness is scored automatically from provided fields.
- Duplicate detection via a deterministic checksum of (entity, document type,
  issue date) — two submissions for the same entity/type/date are flagged.
- Renewal reminders bucketed at 7/30/60/90 days out; auto-expiry once past the
  expiry date (daily job).
- Approval workflow (draft → pending_review → approved/rejected) enforced by
  the workflow engine, with role-gated approve/reject actions.

### Workflow engine
- Configurable, data-driven workflows: `WorkflowDefinition` → `WorkflowState` →
  `WorkflowTransition`, each transition optionally requiring specific roles
  and/or required fields (e.g. resolving a case requires `resolution_evidence`).
- Every transition — including the very first, from nothing to a workflow's
  initial state — is recorded as an immutable, append-only `WorkflowEvent`.
  Current state is always *derived* from the latest event, never stored
  redundantly, so it cannot drift out of sync with history.
- Background jobs are idempotent: each run of the daily/monthly job claims a
  `JobRun` row under a unique `(job_name, run_key)` constraint before doing
  any work, so retries or duplicate triggers are no-ops.

### Controls and audits
- A control library (owner, reviewer, frequency, procedure, evidence
  requirement). Sample-based tests record a pass/fail result, notes, and an
  evidence reference; a second role signs off.
- Failed tests can spawn remediation tasks (owner, due date, status).
- Every mutating action across the platform writes an `AuditLog` row: actor,
  timestamp, entity type/id, action, before/after JSON, and a correlation ID
  tying it back to the originating request. Audit rows are never updated or
  deleted at the application layer.

### Dashboards
- Open/overdue case counts (by priority), SLA attainment (rate + trend),
  document expiry/renewal buckets, control pass rate (overall and per
  control), remediation status, exception aging, and workload by owner.
- Every metric is backed by a real SQL aggregation (see
  `backend/app/services/dashboards.py`) and every tile links to the exact
  list-view filter that reproduces its number — verified in
  `backend/tests/integration/test_dashboards_api.py` and exercised end-to-end
  in `tests/e2e/specs/dashboard-filtering.spec.ts`.

### Financial-operations demo workspace
- Synthetic dealers, clients, onboarding records, accounts, and contacts.
- Simplified W-8/W-9 completeness, expiry, and renewal modeling.
- Simplified FATCA/CRS/QI classification and review-due monitoring —
  explicitly labeled educational, not legal or tax advice (see
  `docs/security-and-limitations.md`).
- Fund-fact-sheet and maturity-notice distribution tracking with
  sent/acknowledged/failed status.

### Security and reliability
- Five roles: Operations Analyst, Reviewer, Compliance Officer, Auditor,
  Admin. Role checks are enforced server-side per endpoint.
- Bcrypt password hashing, JWT bearer tokens, Pydantic input validation on
  every request body, optimistic locking (`version` column) on entities,
  documents, and cases, structured JSON request logs with a correlation ID,
  and `/health` + `/health/ready` endpoints.

## Non-functional requirements
- Deterministic, synthetic demo data only — no real personal data.
- ≥80% automated test coverage on backend domain logic (achieved: 93%, see
  `docs/test-plan.md`).
- Reproducible local setup via Docker Compose; a single seed command produces
  the same dataset every time (fixed RNG seed).

## Out of scope
- Multi-tenant workspace isolation (the demo ships a single financial-ops
  workspace built on an industry-neutral schema).
- Real document storage/OCR — only metadata and a sample-file reference are
  stored (see `docs/security-and-limitations.md`).
- Production-grade secrets management, SSO, or MFA.
