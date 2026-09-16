"""Financial-operations demo workspace: classifications and distributions.

Educational / simplified modeling only — not legal, tax, or regulatory advice.
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.models.enums import (
    ClassificationStatus,
    DistributionKind,
    DistributionStatus,
    RegimeType,
    str_enum,
)

if TYPE_CHECKING:
    from app.models.entity import Entity


class Classification(Base, TimestampMixin):
    """Simplified FATCA / CRS / QI classification and monitoring status."""

    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), nullable=False, index=True)
    regime: Mapped[RegimeType] = mapped_column(str_enum(RegimeType, 8), nullable=False)
    status: Mapped[ClassificationStatus] = mapped_column(
        str_enum(ClassificationStatus, 32),
        default=ClassificationStatus.NOT_STARTED,
    )
    classification_value: Mapped[str | None] = mapped_column(String(128))
    effective_date: Mapped[date | None] = mapped_column(Date)
    review_due_date: Mapped[date | None] = mapped_column(Date, index=True)

    entity: Mapped["Entity"] = relationship()  # noqa: F821


class Distribution(Base, TimestampMixin):
    """Fund fact sheet / maturity notice distribution tracking."""

    __tablename__ = "distributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[DistributionKind] = mapped_column(str_enum(DistributionKind, 32), nullable=False)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), nullable=False, index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    reference_name: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[DistributionStatus] = mapped_column(
        str_enum(DistributionStatus, 16), default=DistributionStatus.PENDING
    )
    channel: Mapped[str] = mapped_column(String(32), default="email")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    entity: Mapped["Entity"] = relationship()  # noqa: F821
