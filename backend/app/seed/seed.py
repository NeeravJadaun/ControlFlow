"""Deterministic synthetic demo-data generator for the financial-operations workspace.

Everything here is fully synthetic (Faker + a fixed RNG seed). Re-running this
script is idempotent: if any seed data already exists it exits without
duplicating rows, unless --reset is passed, which truncates all
seed-managed tables first.

Usage:
    python -m app.seed.seed [--reset]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import UTC, datetime, timedelta

from faker import Faker
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models import Base
from app.models.audit import EscalationRule
from app.models.case import Case, CaseComment, CaseQueue
from app.models.control import Control, ControlTest, RemediationTask
from app.models.document import Document, DocumentType
from app.models.entity import Account, Contact, Entity, RecordType
from app.models.enums import (
    CasePriority,
    CaseStatus,
    ClassificationStatus,
    ControlFrequency,
    ControlResult,
    DistributionKind,
    DistributionStatus,
    EntityKind,
    RegimeType,
    RemediationStatus,
    ReviewStatus,
    Role,
    WorkflowEntityType,
)
from app.models.financial import Classification, Distribution
from app.models.user import User
from app.models.workflow import WorkflowDefinition, WorkflowEvent, WorkflowState, WorkflowTransition
from app.services import classification as classification_service
from app.services import renewal, sla
from app.services.workflow_engine import initiate

settings = get_settings()
SEED = settings.demo_seed

JURISDICTIONS = ["US", "GB", "IE", "LU", "SG", "HK", "CA", "DE", "FR", "JP"]
NOW = datetime.now(UTC)
TODAY = NOW.date()

SEED_MANAGED_TABLES = [
    "workflow_events",
    "workflow_transitions",
    "workflow_states",
    "workflow_definitions",
    "job_runs",
    "audit_logs",
    "escalation_rules",
    "remediation_tasks",
    "control_tests",
    "controls",
    "case_attachments",
    "case_comments",
    "saved_views",
    "cases",
    "case_queues",
    "distributions",
    "classifications",
    "documents",
    "document_types",
    "contacts",
    "accounts",
    "entities",
    "record_types",
    "users",
]


def reset_database(db: Session) -> None:
    table_list = ", ".join(SEED_MANAGED_TABLES)
    db.execute(text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE"))
    db.commit()


def already_seeded(db: Session) -> bool:
    return db.query(User).count() > 0


# ---------------------------------------------------------------------------
# Reference data: workflows, users, record types, queues, document types
# ---------------------------------------------------------------------------


def seed_workflows(db: Session) -> dict[str, WorkflowDefinition]:
    doc_wf = WorkflowDefinition(
        key="document-approval", name="Document Approval", entity_type=WorkflowEntityType.DOCUMENT
    )
    db.add(doc_wf)
    db.flush()
    states = {
        "draft": WorkflowState(workflow_id=doc_wf.id, key="draft", name="Draft", is_initial=True),
        "pending_review": WorkflowState(
            workflow_id=doc_wf.id, key="pending_review", name="Pending Review"
        ),
        "approved": WorkflowState(
            workflow_id=doc_wf.id, key="approved", name="Approved", is_terminal=True
        ),
        "rejected": WorkflowState(
            workflow_id=doc_wf.id, key="rejected", name="Rejected", is_terminal=True
        ),
    }
    db.add_all(states.values())
    db.flush()
    db.add_all(
        [
            WorkflowTransition(
                workflow_id=doc_wf.id,
                key="submit",
                name="Submit for Review",
                from_state_id=states["draft"].id,
                to_state_id=states["pending_review"].id,
            ),
            WorkflowTransition(
                workflow_id=doc_wf.id,
                key="approve",
                name="Approve",
                from_state_id=states["pending_review"].id,
                to_state_id=states["approved"].id,
                required_roles=[Role.REVIEWER.value, Role.COMPLIANCE_OFFICER.value],
            ),
            WorkflowTransition(
                workflow_id=doc_wf.id,
                key="reject",
                name="Reject",
                from_state_id=states["pending_review"].id,
                to_state_id=states["rejected"].id,
                required_roles=[Role.REVIEWER.value, Role.COMPLIANCE_OFFICER.value],
            ),
            WorkflowTransition(
                workflow_id=doc_wf.id,
                key="submit",
                name="Resubmit",
                from_state_id=states["rejected"].id,
                to_state_id=states["pending_review"].id,
            ),
        ]
    )

    case_wf = WorkflowDefinition(
        key="case-lifecycle", name="Case Lifecycle", entity_type=WorkflowEntityType.CASE
    )
    db.add(case_wf)
    db.flush()
    cstates = {
        "open": WorkflowState(workflow_id=case_wf.id, key="open", name="Open", is_initial=True),
        "in_progress": WorkflowState(workflow_id=case_wf.id, key="in_progress", name="In Progress"),
        "pending_review": WorkflowState(
            workflow_id=case_wf.id, key="pending_review", name="Pending Review"
        ),
        "escalated": WorkflowState(workflow_id=case_wf.id, key="escalated", name="Escalated"),
        "resolved": WorkflowState(workflow_id=case_wf.id, key="resolved", name="Resolved"),
        "closed": WorkflowState(
            workflow_id=case_wf.id, key="closed", name="Closed", is_terminal=True
        ),
    }
    db.add_all(cstates.values())
    db.flush()
    transitions = [
        ("start", "Start Work", "open", "in_progress", []),
        ("start", "Resume Work", "escalated", "in_progress", []),
        ("submit_for_review", "Submit for Review", "in_progress", "pending_review", []),
        ("resolve", "Resolve", "in_progress", "resolved", ["resolution_evidence"]),
        ("resolve", "Resolve", "pending_review", "resolved", ["resolution_evidence"]),
        ("resolve", "Resolve", "escalated", "resolved", ["resolution_evidence"]),
        ("escalate", "Escalate", "open", "escalated", []),
        ("escalate", "Escalate", "in_progress", "escalated", []),
        ("escalate", "Escalate", "pending_review", "escalated", []),
        ("escalate", "Escalate Further", "escalated", "escalated", []),
        ("reopen", "Reopen", "escalated", "open", []),
        ("reopen", "Reopen", "resolved", "open", []),
        (
            "close",
            "Close",
            "resolved",
            "closed",
            [],
        ),
    ]
    for key, name, frm, to, req_fields in transitions:
        db.add(
            WorkflowTransition(
                workflow_id=case_wf.id,
                key=key,
                name=name,
                from_state_id=cstates[frm].id,
                to_state_id=cstates[to].id,
                required_fields=req_fields,
                required_roles=(
                    [Role.COMPLIANCE_OFFICER.value, Role.ADMIN.value] if key == "close" else []
                ),
            )
        )
    db.flush()
    return {"document-approval": doc_wf, "case-lifecycle": case_wf}


def seed_users(db: Session) -> dict[str, User]:
    demo_users = [
        ("admin@controlflow.demo", "Ada Admin", Role.ADMIN, "Admin123!"),
        (
            "compliance.officer@controlflow.demo",
            "Carla Compliance",
            Role.COMPLIANCE_OFFICER,
            "Compliance123!",
        ),
        ("reviewer@controlflow.demo", "Raj Reviewer", Role.REVIEWER, "Reviewer123!"),
        ("reviewer2@controlflow.demo", "Rosa Reviewer", Role.REVIEWER, "Reviewer123!"),
        ("auditor@controlflow.demo", "Amara Auditor", Role.AUDITOR, "Auditor123!"),
        ("analyst@controlflow.demo", "Alex Analyst", Role.OPERATIONS_ANALYST, "Analyst123!"),
        ("analyst2@controlflow.demo", "Amina Analyst", Role.OPERATIONS_ANALYST, "Analyst123!"),
        ("analyst3@controlflow.demo", "Anton Analyst", Role.OPERATIONS_ANALYST, "Analyst123!"),
    ]
    users: dict[str, User] = {}
    for email, name, role, password in demo_users:
        user = User(email=email, full_name=name, hashed_password=hash_password(password), role=role)
        db.add(user)
        users[email] = user
    db.flush()
    return users


def seed_record_types(db: Session) -> dict[str, RecordType]:
    types = {
        "dealer": RecordType(
            key="dealer",
            name="Dealer",
            description="Financial intermediary firm distributing products to clients.",
            field_schema={"fields": ["jurisdiction", "entity_type", "qi_agreement_on_file"]},
        ),
        "client": RecordType(
            key="client",
            name="Client",
            description="Individual or corporate account holder.",
            field_schema={"fields": ["jurisdiction", "entity_type", "tax_residency_country"]},
        ),
        "onboarding_record": RecordType(
            key="onboarding_record",
            name="Onboarding Record",
            description="A prospective client or dealer relationship still being onboarded.",
            field_schema={"fields": ["jurisdiction", "entity_type", "tax_residency_country"]},
        ),
    }
    db.add_all(types.values())
    db.flush()
    return types


def seed_case_queues(db: Session) -> dict[str, CaseQueue]:
    queues = {
        "operations": CaseQueue(key="operations", name="Operations", default_sla_hours=48),
        "document-review": CaseQueue(
            key="document-review", name="Document Review", default_sla_hours=48
        ),
        "onboarding": CaseQueue(key="onboarding", name="Client Onboarding", default_sla_hours=72),
        "compliance-monitoring": CaseQueue(
            key="compliance-monitoring", name="Compliance Monitoring", default_sla_hours=48
        ),
        "control-testing": CaseQueue(
            key="control-testing", name="Control Testing", default_sla_hours=120
        ),
        "escalations": CaseQueue(key="escalations", name="Escalations", default_sla_hours=24),
    }
    db.add_all(queues.values())
    db.flush()
    return queues


DOCUMENT_TYPE_DEFS = [
    (
        "w8ben",
        "W-8BEN (Individual)",
        "tax_form",
        ["signature", "country_of_residence", "tax_id"],
        True,
        1095,
    ),
    (
        "w8bene",
        "W-8BEN-E (Entity)",
        "tax_form",
        ["signature", "entity_type", "tax_id", "fatca_status"],
        True,
        1095,
    ),
    ("w9", "W-9 (US Person)", "tax_form", ["signature", "tin", "name_match"], True, 1095),
    (
        "kyc_onboarding_pack",
        "KYC Onboarding Pack",
        "kyc",
        ["id_verification", "address_proof", "source_of_funds"],
        False,
        None,
    ),
    (
        "fatca_self_certification",
        "FATCA Self-Certification",
        "classification",
        ["signature", "fatca_status"],
        True,
        1095,
    ),
    (
        "crs_self_certification",
        "CRS Self-Certification",
        "classification",
        ["signature", "tax_residency_country"],
        True,
        1095,
    ),
    ("qi_agreement", "QI Agreement", "qi", ["signature", "qi_employer_id"], True, 1095),
]


def seed_document_types(db: Session) -> dict[str, DocumentType]:
    types = {}
    for key, name, category, required, expiry, renewal_days in DOCUMENT_TYPE_DEFS:
        dt = DocumentType(
            key=key,
            name=name,
            category=category,
            required_fields=required,
            expiry_applicable=expiry,
            renewal_period_days=renewal_days,
        )
        db.add(dt)
        types[key] = dt
    db.flush()
    return types


def seed_escalation_rules(db: Session) -> None:
    db.add_all(
        [
            EscalationRule(
                key="overdue-24h",
                applies_to="case",
                overdue_hours_threshold=24,
                action="escalate",
                target_role=Role.COMPLIANCE_OFFICER.value,
            ),
            EscalationRule(
                key="overdue-72h-critical",
                applies_to="case",
                overdue_hours_threshold=72,
                action="escalate",
                target_role=Role.COMPLIANCE_OFFICER.value,
            ),
        ]
    )
    db.flush()


CONTROL_DEFS = [
    ("doc-completeness-review", "Document Completeness Review", ControlFrequency.DAILY, "kyc"),
    (
        "fatca-classification-accuracy",
        "FATCA Classification Accuracy",
        ControlFrequency.MONTHLY,
        "compliance",
    ),
    (
        "crs-reportable-threshold",
        "CRS Reportable Threshold Check",
        ControlFrequency.MONTHLY,
        "compliance",
    ),
    (
        "qi-agreement-currency",
        "QI Agreement Currency Check",
        ControlFrequency.QUARTERLY,
        "compliance",
    ),
    (
        "fund-fact-sheet-timeliness",
        "Fund Fact Sheet Distribution Timeliness",
        ControlFrequency.MONTHLY,
        "distribution",
    ),
    (
        "maturity-notice-delivery",
        "Maturity Notice Delivery Confirmation",
        ControlFrequency.MONTHLY,
        "distribution",
    ),
    ("access-review", "User Access Review", ControlFrequency.QUARTERLY, "security"),
    (
        "segregation-of-duties",
        "Segregation of Duties Review",
        ControlFrequency.QUARTERLY,
        "security",
    ),
    ("data-retention", "Data Retention Compliance", ControlFrequency.ANNUAL, "security"),
    ("case-sla-adherence", "Case SLA Adherence Review", ControlFrequency.WEEKLY, "operations"),
    ("duplicate-document-review", "Duplicate Document Review", ControlFrequency.WEEKLY, "kyc"),
    (
        "onboarding-cycle-time",
        "Onboarding Cycle Time Review",
        ControlFrequency.MONTHLY,
        "operations",
    ),
    ("expired-document-remediation", "Expired Document Remediation", ControlFrequency.DAILY, "kyc"),
    ("audit-log-integrity", "Audit Log Integrity Check", ControlFrequency.MONTHLY, "security"),
    (
        "classification-review-due",
        "Classification Review-Due Monitoring",
        ControlFrequency.MONTHLY,
        "compliance",
    ),
]


def seed_controls(db: Session, users: dict[str, User], rnd: random.Random) -> list[Control]:
    owners = [users["compliance.officer@controlflow.demo"], users["analyst@controlflow.demo"]]
    reviewers = [users["reviewer@controlflow.demo"], users["reviewer2@controlflow.demo"]]
    controls: list[Control] = []
    for i in range(40):
        base_key, base_name, freq, category = CONTROL_DEFS[i % len(CONTROL_DEFS)]
        suffix = "" if i < len(CONTROL_DEFS) else f"-{i // len(CONTROL_DEFS) + 1}"
        control = Control(
            key=f"{base_key}{suffix}",
            name=f"{base_name}{' (' + suffix.strip('-') + ')' if suffix else ''}",
            description=f"Simplified demo control covering {category} risk: {base_name.lower()}.",
            owner_id=rnd.choice(owners).id,
            reviewer_id=rnd.choice(reviewers).id,
            frequency=freq,
            procedure=f"Sample-test evidence for '{base_name}' and record pass/fail with notes.",
            evidence_requirement="Attach sample reference and evidence link.",
            is_active=True,
        )
        db.add(control)
        controls.append(control)
    db.flush()
    return controls


def seed_control_tests(
    db: Session, controls: list[Control], users: dict[str, User], rnd: random.Random
) -> list[ControlTest]:
    testers = [
        users["reviewer@controlflow.demo"],
        users["reviewer2@controlflow.demo"],
        users["auditor@controlflow.demo"],
    ]
    tests: list[ControlTest] = []
    for i in range(100):
        control = controls[i % len(controls)]
        days_back = rnd.randint(0, 180)
        test_date = TODAY - timedelta(days=days_back)
        result = ControlResult.FAIL if rnd.random() < 0.15 else ControlResult.PASS
        tester = rnd.choice(testers)
        test = ControlTest(
            control_id=control.id,
            tester_id=tester.id,
            reviewer_id=control.reviewer_id,
            sample_ref=f"SAMPLE-{control.key.upper()}-{i:04d}",
            test_date=test_date,
            result=result,
            notes=(
                "Automated demo control test result."
                if result == ControlResult.PASS
                else "Exception noted; remediation required."
            ),
            evidence_ref=f"evidence/{control.key}/{test_date.isoformat()}.txt",
        )
        if rnd.random() < 0.6:
            test.signed_off_by_id = control.reviewer_id
            test.signed_off_at = datetime.combine(
                test_date, datetime.min.time(), tzinfo=UTC
            ) + timedelta(days=1)
        db.add(test)
        tests.append(test)
    db.flush()

    for test in tests:
        if test.result == ControlResult.FAIL:
            status = rnd.choice(
                [RemediationStatus.OPEN, RemediationStatus.IN_PROGRESS, RemediationStatus.RESOLVED]
            )
            due_date = test.test_date + timedelta(days=14)
            task = RemediationTask(
                control_test_id=test.id,
                description=f"Remediate exception found in control test {test.sample_ref}.",
                owner_id=test.tester_id,
                due_date=due_date,
                status=status,
            )
            if status == RemediationStatus.RESOLVED:
                task.resolved_at = datetime.combine(
                    due_date, datetime.min.time(), tzinfo=UTC
                ) - timedelta(days=rnd.randint(0, 5))
            db.add(task)
    db.flush()
    return tests


# ---------------------------------------------------------------------------
# Entities, accounts, contacts
# ---------------------------------------------------------------------------


def _entity_attributes(kind: EntityKind, rnd: random.Random, fake: Faker) -> dict:
    jurisdiction = rnd.choice(JURISDICTIONS)
    if kind == EntityKind.DEALER:
        return {
            "entity_type": "financial_institution",
            "tax_residency_country": jurisdiction,
            "us_person": jurisdiction == "US",
            "qi_agreement_on_file": rnd.random() < 0.7,
        }
    entity_type = rnd.choices(
        ["individual", "active_business", "financial_institution"], weights=[0.6, 0.35, 0.05]
    )[0]
    return {
        "entity_type": entity_type,
        "tax_residency_country": jurisdiction,
        "us_person": jurisdiction == "US",
        "qi_agreement_on_file": False,
    }


def seed_entities(
    db: Session, record_types: dict[str, RecordType], rnd: random.Random, fake: Faker
) -> list[Entity]:
    entities: list[Entity] = []
    counts = {EntityKind.DEALER: 30, EntityKind.CLIENT: 230, EntityKind.ONBOARDING_RECORD: 40}
    statuses_by_kind = {
        EntityKind.DEALER: ["active"] * 9 + ["under_review"],
        EntityKind.CLIENT: ["active"] * 8 + ["under_review", "dormant"],
        EntityKind.ONBOARDING_RECORD: ["in_progress"] * 7 + ["pending_documents", "on_hold"],
    }
    for kind, count in counts.items():
        record_type_key = kind.value
        for i in range(count):
            attrs = _entity_attributes(kind, rnd, fake)
            name = (
                f"{fake.company()} {['Securities','Capital','Partners','Advisors'][i % 4]}"
                if kind == EntityKind.DEALER
                else (fake.company() if attrs["entity_type"] != "individual" else fake.name())
            )
            entity = Entity(
                record_type_id=record_types[record_type_key].id,
                kind=kind,
                name=name,
                external_ref=f"{kind.value.upper()[:3]}-{10000 + len(entities)}",
                status=rnd.choice(statuses_by_kind[kind]),
                priority=rnd.choices(["low", "medium", "high"], weights=[0.3, 0.5, 0.2])[0],
                jurisdiction=attrs["tax_residency_country"],
                tags=[attrs["entity_type"]],
                attributes=attrs,
            )
            db.add(entity)
            entities.append(entity)
    db.flush()
    return entities


def seed_accounts(db: Session, entities: list[Entity], rnd: random.Random) -> list[Account]:
    eligible = [e for e in entities if e.kind in (EntityKind.CLIENT, EntityKind.DEALER)]
    accounts: list[Account] = []
    account_number = 100000
    target = 500
    per_entity = {e.id: rnd.choice([1, 1, 2, 2, 3]) for e in eligible}
    while sum(per_entity.values()) > target:
        k = rnd.choice(list(per_entity.keys()))
        if per_entity[k] > 1:
            per_entity[k] -= 1
    while sum(per_entity.values()) < target:
        k = rnd.choice(list(per_entity.keys()))
        per_entity[k] += 1

    account_types = ["custody", "brokerage", "omnibus", "advisory", "retirement"]
    for entity in eligible:
        for _ in range(per_entity[entity.id]):
            account_number += 1
            account = Account(
                entity_id=entity.id,
                account_number=f"ACC-{account_number}",
                account_type=rnd.choice(account_types),
                status=rnd.choices(["open", "closed", "suspended"], weights=[0.85, 0.1, 0.05])[0],
                jurisdiction=entity.jurisdiction,
                attributes={"currency": rnd.choice(["USD", "EUR", "GBP", "SGD"])},
            )
            db.add(account)
            accounts.append(account)
    db.flush()
    return accounts


def seed_contacts(db: Session, entities: list[Entity], rnd: random.Random, fake: Faker) -> None:
    for entity in entities:
        if entity.kind == EntityKind.ONBOARDING_RECORD and rnd.random() < 0.3:
            continue
        for _ in range(rnd.choice([1, 1, 2])):
            db.add(
                Contact(
                    entity_id=entity.id,
                    name=fake.name(),
                    email=fake.company_email(),
                    phone=fake.phone_number(),
                    role=rnd.choice(
                        ["Relationship Manager", "Authorized Signer", "Operations Contact"]
                    ),
                )
            )
    db.flush()


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


def _doc_types_for_entity(kind: EntityKind, attrs: dict) -> list[str]:
    if kind == EntityKind.DEALER:
        return [
            "qi_agreement",
            "fatca_self_certification",
            "crs_self_certification",
            "kyc_onboarding_pack",
        ]
    tax_form = (
        "w9"
        if attrs["us_person"]
        else ("w8bene" if attrs["entity_type"] != "individual" else "w8ben")
    )
    return [tax_form, "kyc_onboarding_pack", "fatca_self_certification", "crs_self_certification"]


# EXPIRED is set directly on the review_status column by the daily monitoring
# job (never as a workflow transition — see app/tasks/monitoring.py), so it's
# intentionally left out here: an expired document keeps "approved" as its
# last real workflow state, exactly like the live auto-expire path does.
DOCUMENT_STATE_PATHS: dict[ReviewStatus, list[tuple[str, str]]] = {
    ReviewStatus.DRAFT: [],
    ReviewStatus.PENDING_REVIEW: [("submit", "pending_review")],
    ReviewStatus.APPROVED: [("submit", "pending_review"), ("approve", "approved")],
    ReviewStatus.REJECTED: [("submit", "pending_review"), ("reject", "rejected")],
    ReviewStatus.EXPIRED: [("submit", "pending_review"), ("approve", "approved")],
}


def _record_document_workflow_path(
    db: Session, workflow: WorkflowDefinition, doc: Document, created_at: datetime
) -> None:
    path = DOCUMENT_STATE_PATHS.get(doc.review_status, [])
    if not path:
        return
    from_state = "draft"
    for i, (transition_key, to_state) in enumerate(path, start=1):
        db.add(
            WorkflowEvent(
                workflow_id=workflow.id,
                entity_type=WorkflowEntityType.DOCUMENT,
                entity_id=doc.id,
                from_state_key=from_state,
                to_state_key=to_state,
                transition_key=transition_key,
                actor_id=doc.uploaded_by_id,
                occurred_at=created_at + timedelta(hours=i),
            )
        )
        from_state = to_state


def seed_documents(
    db: Session,
    entities: list[Entity],
    doc_types: dict[str, DocumentType],
    workflow,
    rnd: random.Random,
) -> tuple[list[Document], dict]:
    documents: list[Document] = []
    scenario_ids: dict = {}
    target = 1000

    plans: list[tuple[Entity, str]] = []
    for entity in entities:
        for key in _doc_types_for_entity(entity.kind, entity.attributes):
            plans.append((entity, key))
    while len(plans) < target:
        entity = rnd.choice(entities)
        key = rnd.choice(list(doc_types.keys()))
        plans.append((entity, key))
    plans = plans[:target]

    for entity, type_key in plans:
        doc_type = doc_types[type_key]
        outcome = rnd.random()

        expiry_date = None
        if doc_type.expiry_applicable and doc_type.renewal_period_days:
            # Pick the expiry bucket directly so a realistic share of documents
            # land in each renewal-reminder window instead of nearly all of
            # them landing far in the future.
            bucket = rnd.choices(
                ["expired", "due_7", "due_30", "due_60", "due_90", "healthy"],
                weights=[0.08, 0.03, 0.05, 0.05, 0.06, 0.73],
            )[0]
            days_to_expiry = {
                "expired": -rnd.randint(1, 120),
                "due_7": rnd.randint(0, 7),
                "due_30": rnd.randint(8, 30),
                "due_60": rnd.randint(31, 60),
                "due_90": rnd.randint(61, 90),
                "healthy": rnd.randint(91, 1000),
            }[bucket]
            expiry_date = TODAY + timedelta(days=days_to_expiry)
            issue_date = expiry_date - timedelta(days=doc_type.renewal_period_days)
        else:
            issue_date = TODAY - timedelta(days=rnd.randint(30, 900))

        provided = dict.fromkeys(doc_type.required_fields, True)
        incomplete = False
        if outcome < 0.08 and doc_type.required_fields:
            incomplete = True
            drop = rnd.sample(
                doc_type.required_fields, k=rnd.randint(1, len(doc_type.required_fields))
            )
            for f in drop:
                provided[f] = False
        score, missing = renewal.compute_completeness(doc_type.required_fields, provided)
        checksum = renewal.compute_checksum(
            entity_id=entity.id, document_type_key=type_key, issue_date=issue_date
        )

        if incomplete:
            review_status = ReviewStatus.DRAFT
        elif expiry_date and expiry_date < TODAY:
            review_status = ReviewStatus.EXPIRED
        else:
            review_status = rnd.choices(
                [
                    ReviewStatus.APPROVED,
                    ReviewStatus.PENDING_REVIEW,
                    ReviewStatus.DRAFT,
                    ReviewStatus.REJECTED,
                ],
                weights=[0.65, 0.18, 0.1, 0.07],
            )[0]

        classification_payload = {}
        if type_key == "fatca_self_certification":
            classification_payload = {
                "fatca_status": classification_service.classify_fatca(entity.attributes)
            }
        elif type_key == "crs_self_certification":
            classification_payload = {
                "crs_status": classification_service.classify_crs(entity.attributes)
            }
        elif type_key == "qi_agreement":
            classification_payload = {
                "qi_status": classification_service.classify_qi(entity.attributes)
            }

        doc = Document(
            document_type_id=doc_type.id,
            entity_id=entity.id,
            jurisdiction=entity.jurisdiction,
            issue_date=issue_date,
            expiry_date=expiry_date,
            review_status=review_status,
            file_ref=f"sample_data/documents/{type_key}_sample.txt",
            checksum=checksum,
            completeness_score=score,
            missing_fields=missing,
            classification=classification_payload,
        )
        db.add(doc)
        db.flush()
        doc_created_at = datetime.combine(issue_date, datetime.min.time(), tzinfo=UTC)
        initiate(
            db,
            workflow,
            WorkflowEntityType.DOCUMENT,
            doc.id,
            comment="Seeded document",
            occurred_at=doc_created_at,
        )
        _record_document_workflow_path(db, workflow, doc, doc_created_at)
        documents.append(doc)

        if "renewal_demo" not in scenario_ids and doc_type.expiry_applicable and expiry_date:
            days_left = (expiry_date - TODAY).days
            if 0 < days_left <= 7:
                scenario_ids["renewal_demo_document_id"] = doc.id
        if (
            "pending_approval_demo" not in scenario_ids
            and review_status == ReviewStatus.PENDING_REVIEW
            and score == 100
        ):
            scenario_ids["pending_approval_demo_document_id"] = doc.id

    # Explicit duplicate-detection scenario: clone a handful of existing documents verbatim.
    duplicate_source_docs = rnd.sample(documents, k=25)
    for src in duplicate_source_docs:
        dup = Document(
            document_type_id=src.document_type_id,
            entity_id=src.entity_id,
            jurisdiction=src.jurisdiction,
            issue_date=src.issue_date,
            expiry_date=src.expiry_date,
            review_status=ReviewStatus.DRAFT,
            file_ref=src.file_ref,
            checksum=src.checksum,
            completeness_score=src.completeness_score,
            missing_fields=src.missing_fields,
            is_duplicate_of_id=src.id,
            classification=src.classification,
        )
        db.add(dup)
        db.flush()
        initiate(
            db, workflow, WorkflowEntityType.DOCUMENT, dup.id, comment="Seeded duplicate document"
        )
        documents.append(dup)
        scenario_ids.setdefault("duplicate_demo_document_id", dup.id)

    db.flush()
    return documents, scenario_ids


# ---------------------------------------------------------------------------
# Classifications and distributions
# ---------------------------------------------------------------------------


def seed_classifications(db: Session, entities: list[Entity], rnd: random.Random) -> dict:
    scenario_ids: dict = {}
    candidates = [e for e in entities if e.kind in (EntityKind.DEALER, EntityKind.CLIENT)]
    sample = rnd.sample(candidates, k=min(150, len(candidates)))
    for entity in sample:
        regimes = [RegimeType.FATCA, RegimeType.CRS]
        if entity.kind == EntityKind.DEALER:
            regimes.append(RegimeType.QI)
        for regime in regimes:
            value = classification_service.classify(regime, entity.attributes)
            has_docs = rnd.random() < 0.75
            review_due = TODAY + timedelta(days=rnd.randint(-30, 400))
            status = classification_service.documentation_status(value, has_docs, review_due, TODAY)
            cl = Classification(
                entity_id=entity.id,
                regime=regime,
                status=status,
                classification_value=value,
                effective_date=TODAY - timedelta(days=rnd.randint(30, 700)),
                review_due_date=review_due,
            )
            db.add(cl)
            db.flush()
            if (
                status == ClassificationStatus.REVIEW_DUE
                and "classification_review_demo_entity_id" not in scenario_ids
            ):
                scenario_ids["classification_review_demo_entity_id"] = entity.id
    db.flush()
    return scenario_ids


def seed_distributions(
    db: Session, entities: list[Entity], accounts: list[Account], rnd: random.Random
) -> None:
    clients = [e for e in entities if e.kind == EntityKind.CLIENT]
    accounts_by_entity: dict[int, list[Account]] = {}
    for a in accounts:
        accounts_by_entity.setdefault(a.entity_id, []).append(a)

    fund_names = [
        "Global Balanced Fund",
        "Short Duration Bond Fund",
        "Emerging Markets Equity Fund",
        "Money Market Fund",
    ]
    for month_back in range(6):
        month_date = TODAY.replace(day=1) - timedelta(days=30 * month_back)
        sample = rnd.sample(clients, k=min(40, len(clients)))
        for entity in sample:
            status = rnd.choices(
                [
                    DistributionStatus.ACKNOWLEDGED,
                    DistributionStatus.SENT,
                    DistributionStatus.PENDING,
                    DistributionStatus.FAILED,
                ],
                weights=[0.55, 0.25, 0.12, 0.08],
            )[0]
            entity_accounts = accounts_by_entity.get(entity.id)
            account_id = rnd.choice(entity_accounts).id if entity_accounts else None
            dist = Distribution(
                kind=DistributionKind.FUND_FACT_SHEET,
                entity_id=entity.id,
                account_id=account_id,
                reference_name=rnd.choice(fund_names),
                effective_date=month_date,
                status=status,
                channel=rnd.choice(["email", "portal", "mail"]),
                sent_at=(
                    datetime.combine(month_date, datetime.min.time(), tzinfo=UTC)
                    if status != DistributionStatus.PENDING
                    else None
                ),
            )
            db.add(dist)

    maturing_accounts = rnd.sample(accounts, k=min(60, len(accounts)))
    for account in maturing_accounts:
        status = rnd.choices(
            [DistributionStatus.ACKNOWLEDGED, DistributionStatus.SENT, DistributionStatus.PENDING],
            weights=[0.5, 0.3, 0.2],
        )[0]
        db.add(
            Distribution(
                kind=DistributionKind.MATURITY_NOTICE,
                entity_id=account.entity_id,
                account_id=account.id,
                reference_name=f"Note maturing on {account.account_number}",
                effective_date=TODAY + timedelta(days=rnd.randint(-60, 60)),
                status=status,
                channel="email",
                sent_at=NOW if status != DistributionStatus.PENDING else None,
            )
        )
    db.flush()


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

# `initiate()` always lands a new case in "open". Anything seeded past that
# needs matching WorkflowEvent rows too, or the workflow engine's derived
# current_state (what the UI uses to decide which action buttons to show)
# silently disagrees with the case's own `status` column.
CASE_STATE_PATHS: dict[CaseStatus, list[tuple[str, str]]] = {
    CaseStatus.OPEN: [],
    CaseStatus.IN_PROGRESS: [("start", "in_progress")],
    CaseStatus.PENDING_REVIEW: [("start", "in_progress"), ("submit_for_review", "pending_review")],
    CaseStatus.ESCALATED: [("escalate", "escalated")],
    CaseStatus.RESOLVED: [("start", "in_progress"), ("resolve", "resolved")],
    CaseStatus.CLOSED: [("start", "in_progress"), ("resolve", "resolved"), ("close", "closed")],
}


def _record_case_workflow_path(
    db: Session, workflow: WorkflowDefinition, case: Case, created_at: datetime, end_time: datetime
) -> None:
    path = CASE_STATE_PATHS.get(case.status, [])
    if not path:
        return
    span = max((end_time - created_at).total_seconds(), 60.0)
    from_state = "open"
    for i, (transition_key, to_state) in enumerate(path, start=1):
        occurred_at = created_at + timedelta(seconds=span * i / (len(path) + 1))
        db.add(
            WorkflowEvent(
                workflow_id=workflow.id,
                entity_type=WorkflowEntityType.CASE,
                entity_id=case.id,
                from_state_key=from_state,
                to_state_key=to_state,
                transition_key=transition_key,
                actor_id=case.owner_id,
                occurred_at=occurred_at,
            )
        )
        from_state = to_state


def seed_cases(
    db: Session,
    entities: list[Entity],
    queues: dict[str, CaseQueue],
    users: dict[str, User],
    workflow,
    rnd: random.Random,
    fake: Faker,
) -> dict:
    scenario_ids: dict = {}
    owners = [
        users["analyst@controlflow.demo"],
        users["analyst2@controlflow.demo"],
        users["analyst3@controlflow.demo"],
        users["reviewer@controlflow.demo"],
    ]
    queue_list = list(queues.values())
    case_types = [
        "general",
        "document_review",
        "onboarding",
        "classification_review",
        "control_testing",
    ]

    status_plan = (
        [CaseStatus.OPEN] * 62
        + [CaseStatus.IN_PROGRESS] * 50
        + [CaseStatus.PENDING_REVIEW] * 25
        + [CaseStatus.ESCALATED] * 25
        + [CaseStatus.RESOLVED] * 63
        + [CaseStatus.CLOSED] * 25
    )
    rnd.shuffle(status_plan)

    for target_status in status_plan:
        entity = rnd.choice(entities)
        queue = rnd.choice(queue_list)
        priority = rnd.choices(
            [CasePriority.LOW, CasePriority.MEDIUM, CasePriority.HIGH, CasePriority.CRITICAL],
            weights=[0.25, 0.45, 0.22, 0.08],
        )[0]
        owner = rnd.choice(owners)
        if target_status in (CaseStatus.RESOLVED, CaseStatus.CLOSED):
            # Full 6-month spread so dashboard trend charts have history to show.
            days_back = rnd.randint(0, 180)
        else:
            # Still-open cases skew recent, so most of the backlog looks current;
            # only a realistic minority sit long enough to be genuinely overdue.
            days_back = rnd.choices(
                [rnd.randint(0, 1), rnd.randint(2, 5), rnd.randint(6, 45)],
                weights=[0.6, 0.25, 0.15],
            )[0]
        created_at = NOW - timedelta(days=days_back, hours=rnd.randint(0, 23))
        due_at = sla.compute_due_at(created_at, queue.default_sla_hours, priority)

        case = Case(
            queue_id=queue.id,
            entity_id=entity.id,
            title=f"{rnd.choice(case_types).replace('_', ' ').title()} — {entity.name}",
            description=fake.sentence(nb_words=12),
            case_type=rnd.choice(case_types),
            priority=priority,
            owner_id=owner.id,
            due_at=due_at,
            escalation_level=0,
        )
        case.created_at = created_at
        db.add(case)
        db.flush()
        initiate(
            db,
            workflow,
            WorkflowEntityType.CASE,
            case.id,
            actor_id=owner.id,
            comment="Seeded case",
            occurred_at=created_at,
        )

        if target_status == CaseStatus.IN_PROGRESS:
            case.status = CaseStatus.IN_PROGRESS
        elif target_status == CaseStatus.PENDING_REVIEW:
            case.status = CaseStatus.PENDING_REVIEW
        elif target_status == CaseStatus.ESCALATED:
            case.status = CaseStatus.ESCALATED
            case.escalation_level = rnd.choice([1, 1, 2])
            if case.priority == CasePriority.LOW:
                case.priority = CasePriority.HIGH
            db.add(
                CaseComment(
                    case_id=case.id,
                    author_id=None,
                    body=(
                        "Auto-escalated: overdue past SLA threshold. "
                        f"Escalation level {case.escalation_level}."
                    ),
                )
            )
            if "escalation_demo_case_id" not in scenario_ids:
                case.due_at = NOW - timedelta(hours=96)
                scenario_ids["escalation_demo_case_id"] = case.id
        elif target_status in (CaseStatus.RESOLVED, CaseStatus.CLOSED):
            resolved_offset_hours = (
                rnd.randint(-72, -1) if rnd.random() < 0.7 else rnd.randint(1, 96)
            )
            resolved_at = due_at + timedelta(hours=resolved_offset_hours)
            if resolved_at < created_at:
                resolved_at = created_at + timedelta(hours=rnd.randint(1, 48))
            resolved_at = min(resolved_at, NOW)
            case.status = target_status
            case.resolution_evidence = fake.sentence(nb_words=15)
            case.resolved_at = resolved_at

        _record_case_workflow_path(
            db, workflow, case, created_at, case.resolved_at or min(NOW, case.due_at or NOW)
        )

        now_for_sla = NOW
        case.sla_breached = sla.is_breached(case.status, case.due_at, case.resolved_at, now_for_sla)

        if (
            case.status in (CaseStatus.OPEN, CaseStatus.IN_PROGRESS, CaseStatus.PENDING_REVIEW)
            and not case.sla_breached
            and rnd.random() < 0.12
        ):
            case.due_at = NOW - timedelta(hours=rnd.randint(1, 72))
            case.sla_breached = True
            if "overdue_demo_case_id" not in scenario_ids:
                scenario_ids["overdue_demo_case_id"] = case.id

        if "resolution_demo_case_id" not in scenario_ids and case.status == CaseStatus.IN_PROGRESS:
            scenario_ids["resolution_demo_case_id"] = case.id

    db.flush()
    return scenario_ids


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run(reset: bool = False) -> None:
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    fake = Faker()
    Faker.seed(SEED)
    rnd = random.Random(SEED)
    try:
        if reset:
            print("Resetting seed-managed tables...")
            reset_database(db)
        if already_seeded(db):
            print("Database already contains seed data; skipping (use --reset to regenerate).")
            return

        print("Seeding workflows...")
        workflows = seed_workflows(db)
        print("Seeding users...")
        users = seed_users(db)
        print("Seeding record types, queues, document types, escalation rules...")
        record_types = seed_record_types(db)
        queues = seed_case_queues(db)
        doc_types = seed_document_types(db)
        seed_escalation_rules(db)

        print("Seeding controls and control tests...")
        controls = seed_controls(db, users, rnd)
        seed_control_tests(db, controls, users, rnd)

        print("Seeding entities, accounts, contacts...")
        entities = seed_entities(db, record_types, rnd, fake)
        accounts = seed_accounts(db, entities, rnd)
        seed_contacts(db, entities, rnd, fake)

        print("Seeding documents (completeness, duplicates, expiry)...")
        _documents, doc_scenarios = seed_documents(
            db, entities, doc_types, workflows["document-approval"], rnd
        )

        print("Seeding classifications and distributions...")
        class_scenarios = seed_classifications(db, entities, rnd)
        seed_distributions(db, entities, accounts, rnd)

        print("Seeding cases (6 months of history)...")
        case_scenarios = seed_cases(
            db, entities, queues, users, workflows["case-lifecycle"], rnd, fake
        )

        db.commit()

        scenarios = {**doc_scenarios, **class_scenarios, **case_scenarios}
        summary = {
            "users": db.query(User).count(),
            "entities": db.query(Entity).count(),
            "accounts": db.query(Account).count(),
            "contacts": db.query(Contact).count(),
            "documents": db.query(Document).count(),
            "cases": db.query(Case).count(),
            "controls": db.query(Control).count(),
            "control_tests": db.query(ControlTest).count(),
            "classifications": db.query(Classification).count(),
            "distributions": db.query(Distribution).count(),
            "demo_scenarios": scenarios,
        }
        print(json.dumps(summary, indent=2))

        os.makedirs("sample_data", exist_ok=True)
        with open("sample_data/demo_scenarios.json", "w") as f:
            json.dump(summary, f, indent=2)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ControlFlow demo data")
    parser.add_argument("--reset", action="store_true", help="Truncate seed-managed tables first")
    args = parser.parse_args()
    run(reset=args.reset)


if __name__ == "__main__":
    main()
    sys.exit(0)
