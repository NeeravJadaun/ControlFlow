from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import EntityKind


class RecordTypeOut(BaseModel):
    id: int
    key: str
    name: str
    description: str | None
    field_schema: dict

    model_config = {"from_attributes": True}


class EntityCreate(BaseModel):
    record_type_id: int
    kind: EntityKind
    name: str = Field(min_length=1, max_length=255)
    external_ref: str | None = None
    status: str = "active"
    priority: str = "medium"
    owner_id: int | None = None
    jurisdiction: str | None = None
    tags: list[str] = Field(default_factory=list)
    attributes: dict = Field(default_factory=dict)


class EntityUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    priority: str | None = None
    owner_id: int | None = None
    jurisdiction: str | None = None
    tags: list[str] | None = None
    attributes: dict | None = None
    version: int


class EntityOut(BaseModel):
    id: int
    record_type_id: int
    kind: EntityKind
    name: str
    external_ref: str | None
    status: str
    priority: str
    owner_id: int | None
    jurisdiction: str | None
    tags: list[str]
    attributes: dict
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountOut(BaseModel):
    id: int
    entity_id: int
    account_number: str
    account_type: str
    status: str
    jurisdiction: str | None
    attributes: dict
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactOut(BaseModel):
    id: int
    entity_id: int
    name: str
    email: str | None
    phone: str | None
    role: str | None

    model_config = {"from_attributes": True}
