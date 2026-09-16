# Data Dictionary

Generated from `backend/app/models/`. All tables have `created_at` /
`updated_at` timestamps unless noted; `id` is always a serial primary key.
Enums are stored as `VARCHAR` (not native Postgres enums) via the
`str_enum()` helper (`app/models/enums.py`) so they persist the Python
enum's lowercase `.value`, matching the JSON API — see the note in that file
for why this matters (SQLAlchemy's default is the enum *name*, which would
silently diverge from the API's lowercase values).

## Identity

### `users`
| Column | Type | Notes |
|---|---|---|
| email | string, unique | login identifier |
| full_name | string | |
| hashed_password | string | bcrypt |
| role | enum | operations_analyst · reviewer · compliance_officer · auditor · admin |
| is_active | bool | inactive users cannot log in |
| version | int | optimistic lock (not currently enforced on User writes) |

## Records: entities, accounts, contacts

### `record_types`
Configurable record type definitions (`key`, `name`, `description`,
`field_schema` JSONB). Seeded: `dealer`, `client`, `onboarding_record`.

### `entities`
The generic "record" — a dealer, client, or onboarding record.
| Column | Type | Notes |
|---|---|---|
| record_type_id | FK → record_types | |
| kind | enum | dealer · client · onboarding_record |
| name, external_ref, status, priority | string | |
| owner_id | FK → users, nullable | |
| jurisdiction | string(8) | ISO-ish country code |
| tags | array(string) | |
| attributes | JSONB | type-specific fields, e.g. `us_person`, `entity_type`, `tax_residency_country`, `qi_agreement_on_file` |
| version | int | **optimistic lock** — `PATCH` requires a matching version |

### `accounts`
| Column | Type | Notes |
|---|---|---|
| entity_id | FK → entities | |
| account_number | string, unique | |
| account_type, status, jurisdiction | string | |
| attributes | JSONB | e.g. `currency` |
| version | int | optimistic lock |

### `contacts`
`entity_id`, `name`, `email`, `phone`, `role` (e.g. "Relationship Manager").

## Documents

### `document_types`
`key`, `name`, `category`, `required_fields` (JSON list), `expiry_applicable`
(bool), `renewal_period_days`. Seeded: `w8ben`, `w8bene`, `w9`,
`kyc_onboarding_pack`, `fatca_self_certification`, `crs_self_certification`,
`qi_agreement`.

### `documents`
| Column | Type | Notes |
|---|---|---|
| document_type_id, entity_id | FK | |
| jurisdiction, issue_date, expiry_date | | |
| version_number | int | document *revision* number (renewals increment this) |
| review_status | enum | draft · pending_review · approved · rejected · expired |
| approver_id, uploaded_by_id | FK → users, nullable | |
| file_ref | string | path/reference only — **no binary file storage** |
| checksum | string(64) | `sha256(entity_id:document_type_key:issue_date)` — duplicate-detection key |
| completeness_score | int 0–100 | derived from `required_fields` vs. provided fields at creation |
| missing_fields | JSONB list | |
| is_duplicate_of_id | FK → documents, nullable | set when checksum matches an existing document for the same entity |
| classification | JSONB | e.g. `{"fatca_status": "Active NFFE"}` |
| version | int | **optimistic lock** — approve/reject require a matching version |

## Cases

### `case_queues`
`key`, `name`, `description`, `default_sla_hours`.

### `cases`
| Column | Type | Notes |
|---|---|---|
| queue_id | FK → case_queues | |
| entity_id | FK → entities, nullable | |
| title, description, case_type | | |
| status | enum | open · in_progress · pending_review · escalated · resolved · closed |
| priority | enum | low · medium · high · critical — scales the SLA window (0.25x–2x) |
| owner_id | FK → users, nullable | |
| due_at | timestamptz | computed at creation from queue SLA hours × priority multiplier |
| sla_breached | bool | recomputed daily by the monitoring job **and** on resolve |
| escalation_level | int | incremented each escalation |
| resolution_evidence | text | required to resolve |
| resolved_at | timestamptz | |
| version | int | **optimistic lock** |

### `case_comments`, `case_attachments`
Free-text comments (`author_id` nullable — system-authored auto-escalation
comments have no author) and attachment **metadata only** (`filename`,
`content_type`, `size_bytes`, `storage_ref`) — no binary content is stored.

### `saved_views`
Per-user (`owner_id`) named filter presets: `entity_type`, `filters` (JSONB).

## Workflow engine

`workflow_definitions`, `workflow_states`, `workflow_transitions`,
`workflow_events` — see `docs/workflow-design.md` for the full model and
seeded graphs. `workflow_events` is append-only: nothing in the codebase
issues an `UPDATE` or `DELETE` against it.

## Controls and audit

### `controls`
`key`, `name`, `description`, `owner_id`, `reviewer_id`, `frequency` (daily ·
weekly · monthly · quarterly · annual), `procedure`, `evidence_requirement`,
`is_active`.

### `control_tests`
`control_id`, `tester_id`, `reviewer_id`, `sample_ref`, `test_date`, `result`
(pass · fail), `notes`, `evidence_ref`, `signed_off_by_id`, `signed_off_at`.

### `remediation_tasks`
`control_test_id`, `description`, `owner_id`, `due_date`, `status` (open ·
in_progress · resolved), `resolved_at`.

### `audit_logs`
`actor_id` (nullable — `NULL` means a system/background job), `timestamp`,
`entity_type`, `entity_id`, `action`, `before`/`after` (JSONB, nullable),
`correlation_id`. Indexed on `entity_type`, `entity_id`, `actor_id`,
`timestamp`, `correlation_id` for the audit-log list/filter endpoints.

### `escalation_rules`
`key`, `applies_to`, `overdue_hours_threshold`, `action`, `target_role`,
`is_active`.

### `job_runs`
Idempotency ledger: `job_name`, `run_key`, `status`, `started_at`,
`finished_at`, `result_summary` (JSONB). Unique constraint on `(job_name,
run_key)` is what makes the daily/monthly jobs safe to retry.

## Financial-operations demo workspace

### `classifications`
`entity_id`, `regime` (FATCA · CRS · QI), `status` (not_started ·
pending_documentation · documented · review_due · expired),
`classification_value` (free-text label like "Active NFFE"),
`effective_date`, `review_due_date`.

### `distributions`
`kind` (fund_fact_sheet · maturity_notice), `entity_id`, `account_id`
(nullable), `reference_name`, `effective_date`, `status` (pending · sent ·
acknowledged · failed), `channel`, `sent_at`.

> All financial-workspace tables and their classification logic
> (`services/classification.py`) are explicitly simplified for demonstration
> — see `docs/security-and-limitations.md`.
