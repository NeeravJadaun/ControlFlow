from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import ReviewStatus


class DocumentCreate(BaseModel):
    document_type_id: int
    entity_id: int
    jurisdiction: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    file_ref: str | None = None
    classification: dict = Field(default_factory=dict)
    provided_fields: dict = Field(default_factory=dict)


class DocumentApprove(BaseModel):
    version: int
    comment: str | None = None


class DocumentReject(BaseModel):
    version: int
    reason: str


class DocumentOut(BaseModel):
    id: int
    document_type_id: int
    entity_id: int
    jurisdiction: str | None
    issue_date: date | None
    expiry_date: date | None
    version_number: int
    review_status: ReviewStatus
    approver_id: int | None
    uploaded_by_id: int | None
    file_ref: str | None
    checksum: str | None
    completeness_score: int
    missing_fields: list[str]
    is_duplicate_of_id: int | None
    classification: dict
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentTypeOut(BaseModel):
    id: int
    key: str
    name: str
    category: str
    required_fields: list[str]
    expiry_applicable: bool
    renewal_period_days: int | None

    model_config = {"from_attributes": True}
