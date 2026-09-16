from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.models.enums import CasePriority, CaseStatus, str_enum


class CaseQueue(Base, TimestampMixin):
    __tablename__ = "case_queues"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    default_sla_hours: Mapped[int] = mapped_column(Integer, default=48)


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    queue_id: Mapped[int] = mapped_column(ForeignKey("case_queues.id"), nullable=False, index=True)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    case_type: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        str_enum(CaseStatus, 32), default=CaseStatus.OPEN, index=True
    )
    priority: Mapped[CasePriority] = mapped_column(
        str_enum(CasePriority, 16), default=CasePriority.MEDIUM
    )
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    resolution_evidence: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    queue: Mapped[CaseQueue] = relationship()
    comments: Mapped[list["CaseComment"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["CaseAttachment"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )

    __mapper_args__ = {"version_id_col": version}


class CaseComment(Base, TimestampMixin):
    __tablename__ = "case_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text, nullable=False)

    case: Mapped[Case] = relationship(back_populates="comments")


class CaseAttachment(Base, TimestampMixin):
    __tablename__ = "case_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), default="text/plain")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    case: Mapped[Case] = relationship(back_populates="attachments")


class SavedView(Base, TimestampMixin):
    __tablename__ = "saved_views"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
