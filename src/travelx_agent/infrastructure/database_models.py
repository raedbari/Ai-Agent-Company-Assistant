from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ConversationSessionRecord(Base):
    __tablename__ = "conversation_sessions"
    __table_args__ = (
        Index("ix_conversation_sessions_updated_at", "updated_at"),
    )

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    current_service: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TicketRecord(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_tickets_tenant_id_idempotency_key",
        ),
        UniqueConstraint(
            "tenant_id",
            "ticket_number",
            name="uq_tickets_tenant_id_ticket_number",
        ),
        Index("ix_tickets_tenant_id_status", "tenant_id", "status"),
        Index("ix_tickets_source_session_id", "source_session_id"),
        Index("ix_tickets_created_at", "created_at"),
    )

    ticket_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    ticket_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_draft_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_draft_version: Mapped[int] = mapped_column(Integer, nullable=False)
    service_key: Mapped[str] = mapped_column(String(64), nullable=False)
    assigned_department: Mapped[str] = mapped_column(String(64), nullable=False)
    requirements: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    additional_features: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    customer_notes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TicketAuditEventRecord(Base):
    __tablename__ = "ticket_audit_events"
    __table_args__ = (
        Index("ix_ticket_audit_events_ticket_id", "ticket_id"),
        Index("ix_ticket_audit_events_occurred_at", "occurred_at"),
    )

    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    ticket_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    draft_version: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)