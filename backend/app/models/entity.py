from sqlalchemy import ARRAY, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.models.enums import EntityKind, str_enum


class RecordType(Base, TimestampMixin):
    """Configurable record type definition (dealer, client, contact, ...)."""

    __tablename__ = "record_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    field_schema: Mapped[dict] = mapped_column(JSONB, default=dict)


class Entity(Base, TimestampMixin):
    """A configurable record: dealer, client, contact, or onboarding record."""

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_type_id: Mapped[int] = mapped_column(ForeignKey("record_types.id"), nullable=False)
    kind: Mapped[EntityKind] = mapped_column(str_enum(EntityKind, 32))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    external_ref: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    jurisdiction: Mapped[str | None] = mapped_column(String(8))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(default=1, nullable=False)

    record_type: Mapped[RecordType] = relationship()
    accounts: Mapped[list["Account"]] = relationship(back_populates="entity")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="entity")

    __mapper_args__ = {"version_id_col": version}


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), nullable=False, index=True)
    account_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    account_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    jurisdiction: Mapped[str | None] = mapped_column(String(8))
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(default=1, nullable=False)

    entity: Mapped[Entity] = relationship(back_populates="accounts")

    __mapper_args__ = {"version_id_col": version}


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str | None] = mapped_column(String(64))

    entity: Mapped[Entity] = relationship(back_populates="contacts")
