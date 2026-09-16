"""Import every model so SQLAlchemy's mapper registry and Alembic autogenerate see them."""

from app.db.base_class import Base
from app.models.audit import AuditLog, EscalationRule, JobRun
from app.models.case import Case, CaseAttachment, CaseComment, CaseQueue, SavedView
from app.models.control import Control, ControlTest, RemediationTask
from app.models.document import Document, DocumentType
from app.models.entity import Account, Contact, Entity, RecordType
from app.models.financial import Classification, Distribution
from app.models.user import User
from app.models.workflow import (
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowState,
    WorkflowTransition,
)

__all__ = [
    "Base",
    "User",
    "RecordType",
    "Entity",
    "Account",
    "Contact",
    "DocumentType",
    "Document",
    "CaseQueue",
    "Case",
    "CaseComment",
    "CaseAttachment",
    "SavedView",
    "WorkflowDefinition",
    "WorkflowState",
    "WorkflowTransition",
    "WorkflowEvent",
    "Control",
    "ControlTest",
    "RemediationTask",
    "AuditLog",
    "EscalationRule",
    "JobRun",
    "Classification",
    "Distribution",
]
