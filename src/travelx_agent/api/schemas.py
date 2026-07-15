from pydantic import BaseModel, Field

from travelx_agent.domain.conversation_state import ConversationStage
from travelx_agent.domain.knowledge import KnowledgeSource
from travelx_agent.domain.policy_decision import PolicyAction
from travelx_agent.domain.service_catalog import Department, ServiceKey
from travelx_agent.domain.ticket import Ticket
from travelx_agent.domain.ticket_draft import TicketDraft


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    draft_version: int | None = Field(default=None, ge=1)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    stage: ConversationStage
    policy_action: PolicyAction
    service_key: ServiceKey | None = None
    primary_department: Department | None = None
    missing_requirements: list[str] = Field(default_factory=list)
    ticket_draft: TicketDraft | None = None
    ticket: Ticket | None = None
    knowledge_sources: list[KnowledgeSource] = Field(default_factory=list)

class DepartmentTicketsResponse(BaseModel):
    department: Department
    tickets: list[Ticket] = Field(default_factory=list)