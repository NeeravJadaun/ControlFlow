from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.models.enums import ReviewStatus, str_enum

if TYPE_CHECKING:
    from app.models.entity import Entity


class DocumentType(Base, TimestampMixin):
    __tablename__ = "document_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    required_fields: Mapped[list[str]] = mapped_column(JSONB, default=list)
    expiry_applicable: Mapped[bool] = mapped_column(Boolean, default=False)
    renewal_period_days: Mapped[int | None] = mapped_column(Integer)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type_id: Mapped[int] = mapped_column(
        ForeignKey("document_types.id"), nullable=False, index=True
    )
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), nullable=False, index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(8))
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    review_status: Mapped[ReviewStatus] = mapped_column(
        str_enum(ReviewStatus, 32), default=ReviewStatus.DRAFT
    )
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    file_ref: Mapped[str | None] = mapped_column(String(255))
    checksum: Mapped[str | None] = mapped_column(String(64), index=True)
    completeness_score: Mapped[int] = mapped_column(Integer, default=0)
    missing_fields: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    classification: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    document_type: Mapped[DocumentType] = relationship()
    entity: Mapped["Entity"] = relationship()  # noqa: F821

    __mapper_args__ = {"version_id_col": version}
