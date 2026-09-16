from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.models.enums import ControlFrequency, ControlResult, RemediationStatus, str_enum


class Control(Base, TimestampMixin):
    __tablename__ = "controls"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    frequency: Mapped[ControlFrequency] = mapped_column(
        str_enum(ControlFrequency, 16), nullable=False
    )
    procedure: Mapped[str | None] = mapped_column(Text)
    evidence_requirement: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tests: Mapped[list["ControlTest"]] = relationship(back_populates="control")


class ControlTest(Base, TimestampMixin):
    __tablename__ = "control_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("controls.id"), nullable=False, index=True)
    tester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    sample_ref: Mapped[str | None] = mapped_column(String(128))
    test_date: Mapped[date] = mapped_column(Date, nullable=False)
    result: Mapped[ControlResult] = mapped_column(str_enum(ControlResult, 8), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    evidence_ref: Mapped[str | None] = mapped_column(String(255))
    signed_off_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    signed_off_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    control: Mapped[Control] = relationship(back_populates="tests")
    remediation_tasks: Mapped[list["RemediationTask"]] = relationship(back_populates="control_test")


class RemediationTask(Base, TimestampMixin):
    __tablename__ = "remediation_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    control_test_id: Mapped[int] = mapped_column(
        ForeignKey("control_tests.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[RemediationStatus] = mapped_column(
        str_enum(RemediationStatus, 16), default=RemediationStatus.OPEN
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    control_test: Mapped[ControlTest] = relationship(back_populates="remediation_tasks")
