# Control Library

The demo seeds 40 controls (`backend/app/seed/seed.py::CONTROL_DEFS`, cycled
and suffixed to reach 40) spanning five categories. Each control has an
owner, a reviewer, a testing frequency, a procedure description, and an
evidence requirement. 100 control-test results are generated across them,
spread over the trailing six months, with a fixed 15% fail rate.

## Categories and base controls

| Key | Name | Frequency | Category |
|---|---|---|---|
| `doc-completeness-review` | Document Completeness Review | Daily | KYC |
| `expired-document-remediation` | Expired Document Remediation | Daily | KYC |
| `duplicate-document-review` | Duplicate Document Review | Weekly | KYC |
| `case-sla-adherence` | Case SLA Adherence Review | Weekly | Operations |
| `fatca-classification-accuracy` | FATCA Classification Accuracy | Monthly | Compliance |
| `crs-reportable-threshold` | CRS Reportable Threshold Check | Monthly | Compliance |
| `classification-review-due` | Classification Review-Due Monitoring | Monthly | Compliance |
| `fund-fact-sheet-timeliness` | Fund Fact Sheet Distribution Timeliness | Monthly | Distribution |
| `maturity-notice-delivery` | Maturity Notice Delivery Confirmation | Monthly | Distribution |
| `onboarding-cycle-time` | Onboarding Cycle Time Review | Monthly | Operations |
| `audit-log-integrity` | Audit Log Integrity Check | Monthly | Security |
| `qi-agreement-currency` | QI Agreement Currency Check | Quarterly | Compliance |
| `access-review` | User Access Review | Quarterly | Security |
| `segregation-of-duties` | Segregation of Duties Review | Quarterly | Security |
| `data-retention` | Data Retention Compliance | Annual | Security |

These 15 base definitions are cycled with numeric suffixes — e.g.
`doc-completeness-review`, then `doc-completeness-review-2` on the second
pass — to reach the required 40 active controls, each independently owned,
reviewed, and tested.

## Control-testing workflow

1. **Record a test** (`POST /api/controls/tests`) — Reviewer, Compliance
   Officer, or Auditor role. Captures a sample reference, test date, pass/fail
   result, notes, and an evidence reference (a path string; no binary
   evidence is stored in this demo).
2. **Sign off** (`POST /api/controls/tests/{id}/sign-off`) — Compliance
   Officer or Auditor role, one-time (a second sign-off attempt is rejected
   with 400). Records `signed_off_by_id` and `signed_off_at`.
3. **Remediation** — any authenticated user can open a `RemediationTask`
   against a control test (typically a failed one), with an owner and due
   date. Status moves `open → in_progress → resolved`; resolving stamps
   `resolved_at`.
4. **Monthly automation** — the monthly Celery job checks every
   `frequency=monthly` active control for a test recorded this calendar
   month; if none exists, it opens a case in the `control-testing` queue
   titled "Monthly control test due: {control name}". This is the mechanism
   that keeps monthly testing from silently lapsing.

## Evidence export

`GET /api/controls/evidence/export.csv` (Auditor or Compliance Officer role)
produces one row per control test: control key/name, test date, result,
sample reference, evidence reference, tester, and sign-off actor/timestamp.
This is the "audit-package export" scenario exercised by
`tests/e2e/specs/audit-package-export.spec.ts` and demoed in
`docs/demo-guide.md`.

## Exception aging

The dashboard buckets *open* remediation tasks by how many days past their
due date they are: 0–7, 8–30, 31–60, and 60+ days
(`services/dashboards.py::exception_aging`). This is the leading indicator
surfaced on the operations dashboard for controls that are failing and not
yet being fixed.
