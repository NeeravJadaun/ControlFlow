import pytest
from app.models.enums import Role, WorkflowEntityType
from app.services.workflow_engine import (
    ForbiddenTransitionError,
    InvalidTransitionError,
    MissingFieldsError,
    apply_transition,
    available_transitions,
    current_state_key,
    initiate,
    state_history,
)


def test_new_entity_starts_in_initial_state(db, workflows):
    wf = workflows["document-approval"]
    initiate(db, wf, WorkflowEntityType.DOCUMENT, entity_id=1)
    db.flush()
    assert current_state_key(db, wf, WorkflowEntityType.DOCUMENT, 1) == "draft"


def test_apply_transition_moves_state_and_records_event(db, workflows):
    wf = workflows["document-approval"]
    initiate(db, wf, WorkflowEntityType.DOCUMENT, entity_id=2)
    db.flush()

    apply_transition(
        db,
        wf,
        WorkflowEntityType.DOCUMENT,
        2,
        transition_key="submit",
        actor_role=Role.OPERATIONS_ANALYST,
        actor_id=None,
    )
    db.flush()
    assert current_state_key(db, wf, WorkflowEntityType.DOCUMENT, 2) == "pending_review"

    history = state_history(db, wf, WorkflowEntityType.DOCUMENT, 2)
    assert [e.to_state_key for e in history] == ["draft", "pending_review"]
    assert history[0].from_state_key is None
    assert history[1].from_state_key == "draft"


def test_apply_transition_rejects_invalid_transition(db, workflows):
    wf = workflows["document-approval"]
    initiate(db, wf, WorkflowEntityType.DOCUMENT, entity_id=3)
    db.flush()
    with pytest.raises(InvalidTransitionError):
        apply_transition(
            db,
            wf,
            WorkflowEntityType.DOCUMENT,
            3,
            transition_key="approve",
            actor_role=Role.REVIEWER,
            actor_id=None,
        )


def test_apply_transition_enforces_required_role(db, workflows):
    wf = workflows["document-approval"]
    initiate(db, wf, WorkflowEntityType.DOCUMENT, entity_id=4)
    db.flush()
    apply_transition(
        db,
        wf,
        WorkflowEntityType.DOCUMENT,
        4,
        transition_key="submit",
        actor_role=Role.OPERATIONS_ANALYST,
        actor_id=None,
    )
    db.flush()
    with pytest.raises(ForbiddenTransitionError):
        apply_transition(
            db,
            wf,
            WorkflowEntityType.DOCUMENT,
            4,
            transition_key="approve",
            actor_role=Role.OPERATIONS_ANALYST,
            actor_id=None,
        )


def test_admin_bypasses_required_role(db, workflows):
    wf = workflows["document-approval"]
    initiate(db, wf, WorkflowEntityType.DOCUMENT, entity_id=5)
    db.flush()
    apply_transition(
        db,
        wf,
        WorkflowEntityType.DOCUMENT,
        5,
        transition_key="submit",
        actor_role=Role.OPERATIONS_ANALYST,
        actor_id=None,
    )
    db.flush()
    apply_transition(
        db,
        wf,
        WorkflowEntityType.DOCUMENT,
        5,
        transition_key="approve",
        actor_role=Role.ADMIN,
        actor_id=None,
    )
    db.flush()
    assert current_state_key(db, wf, WorkflowEntityType.DOCUMENT, 5) == "approved"


def test_apply_transition_enforces_required_fields(db, workflows):
    wf = workflows["case-lifecycle"]
    initiate(db, wf, WorkflowEntityType.CASE, entity_id=10)
    db.flush()
    apply_transition(
        db,
        wf,
        WorkflowEntityType.CASE,
        10,
        transition_key="start",
        actor_role=Role.OPERATIONS_ANALYST,
        actor_id=None,
    )
    db.flush()
    with pytest.raises(MissingFieldsError):
        apply_transition(
            db,
            wf,
            WorkflowEntityType.CASE,
            10,
            transition_key="resolve",
            actor_role=Role.OPERATIONS_ANALYST,
            actor_id=None,
        )


def test_apply_transition_succeeds_with_required_fields_provided(db, workflows):
    wf = workflows["case-lifecycle"]
    initiate(db, wf, WorkflowEntityType.CASE, entity_id=11)
    db.flush()
    apply_transition(
        db,
        wf,
        WorkflowEntityType.CASE,
        11,
        transition_key="start",
        actor_role=Role.OPERATIONS_ANALYST,
        actor_id=None,
    )
    db.flush()
    apply_transition(
        db,
        wf,
        WorkflowEntityType.CASE,
        11,
        transition_key="resolve",
        actor_role=Role.OPERATIONS_ANALYST,
        actor_id=None,
        provided_fields={"resolution_evidence": "Confirmed via bank statement."},
    )
    db.flush()
    assert current_state_key(db, wf, WorkflowEntityType.CASE, 11) == "resolved"


def test_available_transitions_filters_by_role(db, workflows):
    wf = workflows["document-approval"]
    initiate(db, wf, WorkflowEntityType.DOCUMENT, entity_id=6)
    db.flush()
    apply_transition(
        db,
        wf,
        WorkflowEntityType.DOCUMENT,
        6,
        transition_key="submit",
        actor_role=Role.OPERATIONS_ANALYST,
        actor_id=None,
    )
    db.flush()
    analyst_transitions = available_transitions(wf, "pending_review", Role.OPERATIONS_ANALYST)
    reviewer_transitions = available_transitions(wf, "pending_review", Role.REVIEWER)
    assert analyst_transitions == []
    assert {t.key for t in reviewer_transitions} == {"approve", "reject"}


def test_workflow_events_are_never_updated_in_place(db, workflows):
    """WorkflowEvent has no update path in the service layer — history only grows."""
    wf = workflows["case-lifecycle"]
    initiate(db, wf, WorkflowEntityType.CASE, entity_id=12)
    db.flush()
    apply_transition(
        db,
        wf,
        WorkflowEntityType.CASE,
        12,
        transition_key="start",
        actor_role=Role.OPERATIONS_ANALYST,
        actor_id=None,
    )
    db.flush()
    history_before = state_history(db, wf, WorkflowEntityType.CASE, 12)
    assert len(history_before) == 2
    ids_before = [e.id for e in history_before]

    apply_transition(
        db,
        wf,
        WorkflowEntityType.CASE,
        12,
        transition_key="escalate",
        actor_role=Role.OPERATIONS_ANALYST,
        actor_id=None,
    )
    db.flush()
    history_after = state_history(db, wf, WorkflowEntityType.CASE, 12)
    assert len(history_after) == 3
    assert [e.id for e in history_after[:2]] == ids_before
