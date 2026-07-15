from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from travelx_agent.domain.service_catalog import ServiceKey
from travelx_agent.domain.ticket import Ticket
from travelx_agent.domain.ticket_draft import TicketDraft


class ConversationStage(StrEnum):
    NEW = "new"
    DISCOVERY = "discovery"
    REQUIREMENTS = "requirements"
    DRAFT_REVIEW = "draft_review"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    TICKET_CREATED = "ticket_created"
    HUMAN_HANDOFF = "human_handoff"
    SUSPENDED = "suspended"


class ConversationCounters(BaseModel):
    exact_repeat_count: int = Field(default=0, ge=0)
    semantic_repeat_count: int = Field(default=0, ge=0)
    rapid_repeat_count: int = Field(default=0, ge=0)
    clarification_attempts: int = Field(default=0, ge=0)
    messages_in_window: int = Field(default=0, ge=0)


class ConversationState(BaseModel):
    session_id: str
    revision: int = Field(default=0, ge=0)
    stage: ConversationStage = ConversationStage.NEW
    current_service: ServiceKey | None = None
    collected_requirements: dict[str, str] = Field(default_factory=dict)
    missing_requirements: list[str] = Field(default_factory=list)
    ticket_draft: TicketDraft | None = None
    created_ticket: Ticket | None = None
    last_question_key: str | None = None
    last_question_text: str | None = None
    last_user_message: str | None = None
    last_assistant_response: str | None = None
    last_semantic_signature: str | None = None
    counters: ConversationCounters = Field(default_factory=ConversationCounters)
    human_verified: bool = False
    suspended_until: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))