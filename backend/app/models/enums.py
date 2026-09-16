"""Shared enumerations for the ControlFlow domain model."""

import enum

from sqlalchemy import Enum as SAEnum


def str_enum(enum_cls: type[enum.Enum], length: int = 32) -> SAEnum:
    """A VARCHAR-backed SQLAlchemy Enum that stores `.value` (not `.name`).

    Plain `sa.Enum(SomeEnum)` persists the member *name*, which would silently
    diverge from the lowercase `.value` strings the API and frontend use.
    """
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda obj: [e.value for e in obj],
    )


class Role(str, enum.Enum):
    OPERATIONS_ANALYST = "operations_analyst"
    REVIEWER = "reviewer"
    COMPLIANCE_OFFICER = "compliance_officer"
    AUDITOR = "auditor"
    ADMIN = "admin"


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class CasePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ControlFrequency(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ControlResult(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"


class RemediationStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class RegimeType(str, enum.Enum):
    FATCA = "FATCA"
    CRS = "CRS"
    QI = "QI"


class ClassificationStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    PENDING_DOCUMENTATION = "pending_documentation"
    DOCUMENTED = "documented"
    REVIEW_DUE = "review_due"
    EXPIRED = "expired"


class DistributionKind(str, enum.Enum):
    FUND_FACT_SHEET = "fund_fact_sheet"
    MATURITY_NOTICE = "maturity_notice"


class DistributionStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"


class EntityKind(str, enum.Enum):
    DEALER = "dealer"
    CLIENT = "client"
    ONBOARDING_RECORD = "onboarding_record"


class WorkflowEntityType(str, enum.Enum):
    CASE = "case"
    DOCUMENT = "document"
