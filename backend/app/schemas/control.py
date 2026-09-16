from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import ControlFrequency, ControlResult, RemediationStatus


class ControlOut(BaseModel):
    id: int
    key: str
    name: str
    description: str | None
    owner_id: int | None
    reviewer_id: int | None
    frequency: ControlFrequency
    procedure: str | None
    evidence_requirement: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class ControlTestCreate(BaseModel):
    control_id: int
    sample_ref: str | None = None
    test_date: date
    result: ControlResult
    notes: str | None = None
    evidence_ref: str | None = None


class ControlTestSignOff(BaseModel):
    pass


class ControlTestOut(BaseModel):
    id: int
    control_id: int
    tester_id: int | None
    reviewer_id: int | None
    sample_ref: str | None
    test_date: date
    result: ControlResult
    notes: str | None
    evidence_ref: str | None
    signed_off_by_id: int | None
    signed_off_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RemediationTaskCreate(BaseModel):
    control_test_id: int
    description: str = Field(min_length=1)
    owner_id: int | None = None
    due_date: date | None = None


class RemediationTaskUpdate(BaseModel):
    status: RemediationStatus


class RemediationTaskOut(BaseModel):
    id: int
    control_test_id: int
    description: str
    owner_id: int | None
    due_date: date | None
    status: RemediationStatus
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
