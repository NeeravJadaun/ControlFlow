from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import ClassificationStatus, DistributionKind, DistributionStatus, RegimeType


class ClassificationOut(BaseModel):
    id: int
    entity_id: int
    regime: RegimeType
    status: ClassificationStatus
    classification_value: str | None
    effective_date: date | None
    review_due_date: date | None

    model_config = {"from_attributes": True}


class DistributionOut(BaseModel):
    id: int
    kind: DistributionKind
    entity_id: int
    account_id: int | None
    reference_name: str
    effective_date: date
    status: DistributionStatus
    channel: str
    sent_at: datetime | None

    model_config = {"from_attributes": True}


class DistributionMarkSent(BaseModel):
    pass
