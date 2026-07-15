from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from travelx_agent.domain.service_catalog import Department, ServiceKey


class TicketStatus(StrEnum):
    NEW = "new"


class TicketAuditEventType(StrEnum):
    CREATED = "created"


class TicketAuditEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: TicketAuditEventType
    actor_type: str = "customer"
    session_id: str
    draft_version: int = Field(ge=1)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Ticket(BaseModel):
    ticket_id: UUID = Field(default_factory=uuid4)
    ticket_number: str
    status: TicketStatus = TicketStatus.NEW
    source_session_id: str
    source_draft_id: UUID
    source_draft_version: int = Field(ge=1)
    service_key: ServiceKey
    assigned_department: Department
    requirements: dict[str, str] = Field(default_factory=dict)
    additional_features: list[str] = Field(default_factory=list)
    customer_notes: list[str] = Field(default_factory=list)
    audit_events: list[TicketAuditEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TicketWriteResult(BaseModel):
    ticket: Ticket
    created: bool


class TicketConfirmationOutcome(StrEnum):
    CREATED = "created"
    ALREADY_CREATED = "already_created"
    VERSION_REQUIRED = "version_required"
    VERSION_CONFLICT = "version_conflict"
    DRAFT_NOT_READY = "draft_not_ready"