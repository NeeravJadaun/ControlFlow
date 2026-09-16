from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.models.enums import WorkflowEntityType, str_enum


class WorkflowDefinition(Base, TimestampMixin):
    __tablename__ = "workflow_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[WorkflowEntityType] = mapped_column(
        str_enum(WorkflowEntityType, 16), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    states: Mapped[list["WorkflowState"]] = relationship(back_populates="workflow")
    transitions: Mapped[list["WorkflowTransition"]] = relationship(back_populates="workflow")


class WorkflowState(Base, TimestampMixin):
    __tablename__ = "workflow_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_definitions.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_initial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)
    sla_hours: Mapped[int | None] = mapped_column(Integer)

    workflow: Mapped[WorkflowDefinition] = relationship(back_populates="states")


class WorkflowTransition(Base, TimestampMixin):
    __tablename__ = "workflow_transitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_definitions.id"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    from_state_id: Mapped[int] = mapped_column(ForeignKey("workflow_states.id"), nullable=False)
    to_state_id: Mapped[int] = mapped_column(ForeignKey("workflow_states.id"), nullable=False)
    required_roles: Mapped[list[str]] = mapped_column(JSONB, default=list)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    required_fields: Mapped[list[str]] = mapped_column(JSONB, default=list)

    workflow: Mapped[WorkflowDefinition] = relationship(back_populates="transitions")
    from_state: Mapped[WorkflowState] = relationship(foreign_keys=[from_state_id])
    to_state: Mapped[WorkflowState] = relationship(foreign_keys=[to_state_id])


class WorkflowEvent(Base):
    """Immutable, append-only workflow transition history."""

    __tablename__ = "workflow_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflow_definitions.id"), nullable=False)
    entity_type: Mapped[WorkflowEntityType] = mapped_column(
        str_enum(WorkflowEntityType, 16), nullable=False
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    from_state_key: Mapped[str | None] = mapped_column(String(64))
    to_state_key: Mapped[str] = mapped_column(String(64), nullable=False)
    transition_key: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
