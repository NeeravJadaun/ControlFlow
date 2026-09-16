"""Configurable workflow engine: statuses, transitions, roles, and an
immutable, append-only event history.

Current state is always derived from the latest WorkflowEvent for a given
(entity_type, entity_id) rather than stored redundantly, so history can never
drift out of sync with "current" state.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Role, WorkflowEntityType
from app.models.workflow import (
    WorkflowDefinition,
    WorkflowEvent,
    WorkflowState,
    WorkflowTransition,
)


class WorkflowError(Exception):
    pass


class InvalidTransitionError(WorkflowError):
    pass


class ForbiddenTransitionError(WorkflowError):
    pass


class MissingFieldsError(WorkflowError):
    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Missing required fields: {', '.join(missing)}")


def get_workflow(db: Session, key: str) -> WorkflowDefinition:
    stmt = select(WorkflowDefinition).where(WorkflowDefinition.key == key)
    workflow = db.execute(stmt).scalar_one()
    return workflow


def current_state_key(
    db: Session, workflow: WorkflowDefinition, entity_type: WorkflowEntityType, entity_id: int
) -> str:
    stmt = (
        select(WorkflowEvent)
        .where(
            WorkflowEvent.workflow_id == workflow.id,
            WorkflowEvent.entity_type == entity_type,
            WorkflowEvent.entity_id == entity_id,
        )
        .order_by(WorkflowEvent.occurred_at.desc(), WorkflowEvent.id.desc())
        .limit(1)
    )
    last_event = db.execute(stmt).scalar_one_or_none()
    if last_event is not None:
        return last_event.to_state_key
    initial = next((s for s in workflow.states if s.is_initial), None)
    if initial is None:
        raise WorkflowError(f"Workflow '{workflow.key}' has no initial state")
    return initial.key


def available_transitions(
    workflow: WorkflowDefinition, from_state_key: str, role: Role
) -> list[WorkflowTransition]:
    result = []
    for t in workflow.transitions:
        if t.from_state.key != from_state_key:
            continue
        if t.required_roles and role.value not in t.required_roles and role != Role.ADMIN:
            continue
        result.append(t)
    return result


def initiate(
    db: Session,
    workflow: WorkflowDefinition,
    entity_type: WorkflowEntityType,
    entity_id: int,
    actor_id: int | None = None,
    comment: str | None = None,
    occurred_at: datetime | None = None,
) -> WorkflowEvent:
    """Records the first, from-nothing WorkflowEvent placing a new entity in its initial state."""
    initial = next((s for s in workflow.states if s.is_initial), None)
    if initial is None:
        raise WorkflowError(f"Workflow '{workflow.key}' has no initial state")
    event = WorkflowEvent(
        workflow_id=workflow.id,
        entity_type=entity_type,
        entity_id=entity_id,
        from_state_key=None,
        to_state_key=initial.key,
        transition_key="create",
        actor_id=actor_id,
        comment=comment,
        occurred_at=occurred_at or datetime.now(UTC),
    )
    db.add(event)
    return event


def apply_transition(
    db: Session,
    workflow: WorkflowDefinition,
    entity_type: WorkflowEntityType,
    entity_id: int,
    transition_key: str,
    actor_role: Role,
    actor_id: int | None,
    provided_fields: dict | None = None,
    comment: str | None = None,
) -> WorkflowEvent:
    from_key = current_state_key(db, workflow, entity_type, entity_id)
    transition = next(
        (
            t
            for t in workflow.transitions
            if t.key == transition_key and t.from_state.key == from_key
        ),
        None,
    )
    if transition is None:
        raise InvalidTransitionError(
            f"No transition '{transition_key}' from state '{from_key}' in workflow '{workflow.key}'"
        )
    if (
        transition.required_roles
        and actor_role.value not in transition.required_roles
        and actor_role != Role.ADMIN
    ):
        raise ForbiddenTransitionError(
            f"Transition '{transition_key}' requires one of roles {transition.required_roles}"
        )
    if transition.required_fields:
        provided = provided_fields or {}
        missing = [f for f in transition.required_fields if not provided.get(f)]
        if missing:
            raise MissingFieldsError(missing)

    event = WorkflowEvent(
        workflow_id=workflow.id,
        entity_type=entity_type,
        entity_id=entity_id,
        from_state_key=from_key,
        to_state_key=transition.to_state.key,
        transition_key=transition_key,
        actor_id=actor_id,
        comment=comment,
        occurred_at=datetime.now(UTC),
    )
    db.add(event)
    return event


def state_history(
    db: Session, workflow: WorkflowDefinition, entity_type: WorkflowEntityType, entity_id: int
) -> list[WorkflowEvent]:
    stmt = (
        select(WorkflowEvent)
        .where(
            WorkflowEvent.workflow_id == workflow.id,
            WorkflowEvent.entity_type == entity_type,
            WorkflowEvent.entity_id == entity_id,
        )
        .order_by(WorkflowEvent.occurred_at.asc(), WorkflowEvent.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def workflow_state_by_key(workflow: WorkflowDefinition, key: str) -> WorkflowState:
    return next(s for s in workflow.states if s.key == key)
