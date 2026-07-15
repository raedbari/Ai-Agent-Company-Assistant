from pydantic import BaseModel, Field

from travelx_agent.domain.conversation_state import ConversationStage
from travelx_agent.domain.knowledge import KnowledgeSource
from travelx_agent.domain.policy_decision import PolicyAction
from travelx_agent.domain.service_catalog import Department, ServiceKey


class AssistantResponse(BaseModel):
    text: str
    policy_action: PolicyAction
    stage: ConversationStage
    service_key: ServiceKey | None = None
    primary_department: Department | None = None
    missing_requirements: list[str] = Field(default_factory=list)
    knowledge_sources: list[KnowledgeSource] = Field(default_factory=list)