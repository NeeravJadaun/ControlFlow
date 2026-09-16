from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_correlation_id, get_current_user, get_db
from app.models.enums import WorkflowEntityType
from app.models.user import User
from app.schemas.workflow import (
    WorkflowEventOut,
    WorkflowStatusOut,
    WorkflowTransitionOut,
)
from app.services.audit_log import record_audit
from app.services.workflow_engine import (
    ForbiddenTransitionError,
    InvalidTransitionError,
    MissingFieldsError,
    WorkflowError,
    apply_transition,
    available_transitions,
    current_state_key,
    get_workflow,
    state_history,
)

router = APIRouter()


@router.get("/{workflow_key}/{entity_type}/{entity_id}", response_model=WorkflowStatusOut)
def get_workflow_status(
    workflow_key: str,
    entity_type: WorkflowEntityType,
    entity_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkflowStatusOut:
    try:
        workflow = get_workflow(db, workflow_key)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Workflow '{workflow_key}' not found"
        ) from exc
    current = current_state_key(db, workflow, entity_type, entity_id)
    transitions = available_transitions(workflow, current, user.role)
    return WorkflowStatusOut(
        workflow_key=workflow_key,
        entity_type=entity_type,
        entity_id=entity_id,
        current_state=current,
        available_transitions=[
            WorkflowTransitionOut(
                key=t.key,
                name=t.name,
                from_state=t.from_state.key,
                to_state=t.to_state.key,
                required_roles=t.required_roles,
                requires_approval=t.requires_approval,
                required_fields=t.required_fields,
            )
            for t in transitions
        ],
    )


@router.get(
    "/{workflow_key}/{entity_type}/{entity_id}/history", response_model=list[WorkflowEventOut]
)
def get_workflow_history(
    workflow_key: str,
    entity_type: WorkflowEntityType,
    entity_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list:
    workflow = get_workflow(db, workflow_key)
    return state_history(db, workflow, entity_type, entity_id)


@router.post(
    "/{workflow_key}/{entity_type}/{entity_id}/transitions", response_model=WorkflowEventOut
)
def transition_entity(
    workflow_key: str,
    entity_type: WorkflowEntityType,
    entity_id: int,
    transition_key: str,
    comment: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    correlation_id: str = Depends(get_correlation_id),
):
    workflow = get_workflow(db, workflow_key)
    try:
        event = apply_transition(
            db,
            workflow,
            entity_type,
            entity_id,
            transition_key=transition_key,
            actor_role=user.role,
            actor_id=user.id,
            comment=comment,
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ForbiddenTransitionError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except MissingFieldsError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except WorkflowError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    record_audit(
        db,
        actor_id=user.id,
        entity_type=entity_type.value,
        entity_id=entity_id,
        action=f"workflow_transition:{transition_key}",
        before={"state": event.from_state_key},
        after={"state": event.to_state_key},
        correlation_id=correlation_id,
    )
    db.commit()
    db.refresh(event)
    return event
