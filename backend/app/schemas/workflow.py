from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import WorkflowEntityType


class TransitionRequest(BaseModel):
    transition_key: str
    provided_fields: dict = Field(default_factory=dict)
    comment: str | None = None


class WorkflowStateOut(BaseModel):
    key: str
    name: str
    is_initial: bool
    is_terminal: bool
    sla_hours: int | None

    model_config = {"from_attributes": True}


class WorkflowTransitionOut(BaseModel):
    key: str
    name: str
    from_state: str
    to_state: str
    required_roles: list[str]
    requires_approval: bool
    required_fields: list[str]


class WorkflowStatusOut(BaseModel):
    workflow_key: str
    entity_type: WorkflowEntityType
    entity_id: int
    current_state: str
    available_transitions: list[WorkflowTransitionOut]


class WorkflowEventOut(BaseModel):
    id: int
    from_state_key: str | None
    to_state_key: str
    transition_key: str
    actor_id: int | None
    comment: str | None
    occurred_at: datetime

    model_config = {"from_attributes": True}
