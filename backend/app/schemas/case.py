from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CasePriority, CaseStatus


class CaseQueueOut(BaseModel):
    id: int
    key: str
    name: str
    description: str | None
    default_sla_hours: int

    model_config = {"from_attributes": True}


class CaseCreate(BaseModel):
    queue_id: int
    entity_id: int | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    case_type: str = "general"
    priority: CasePriority = CasePriority.MEDIUM


class CaseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: CaseStatus | None = None
    priority: CasePriority | None = None
    owner_id: int | None = None
    version: int


class CaseResolve(BaseModel):
    resolution_evidence: str = Field(min_length=1)
    version: int


class CaseCommentCreate(BaseModel):
    body: str = Field(min_length=1)


class CaseCommentOut(BaseModel):
    id: int
    case_id: int
    author_id: int | None
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseAttachmentCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = "text/plain"
    size_bytes: int = Field(default=0, ge=0)


class CaseAttachmentOut(BaseModel):
    id: int
    case_id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseOut(BaseModel):
    id: int
    queue_id: int
    entity_id: int | None
    title: str
    description: str | None
    case_type: str
    status: CaseStatus
    priority: CasePriority
    owner_id: int | None
    due_at: datetime | None
    sla_breached: bool
    escalation_level: int
    resolution_evidence: str | None
    resolved_at: datetime | None
    tags: list[str]
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BulkUpdateRequest(BaseModel):
    case_ids: list[int]
    status: CaseStatus | None = None
    priority: CasePriority | None = None
    owner_id: int | None = None


class SavedViewCreate(BaseModel):
    name: str
    entity_type: str
    filters: dict = Field(default_factory=dict)


class SavedViewOut(BaseModel):
    id: int
    owner_id: int
    name: str
    entity_type: str
    filters: dict

    model_config = {"from_attributes": True}
