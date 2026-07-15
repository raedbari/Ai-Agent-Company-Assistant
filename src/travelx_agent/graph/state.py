from typing import NotRequired, TypedDict

from travelx_agent.application.requirements_collector import RequirementCollectionResult
from travelx_agent.application.ticket_creation_service import TicketConfirmationResult
from travelx_agent.domain.assistant_response import AssistantResponse
from travelx_agent.domain.conversation_state import ConversationState
from travelx_agent.domain.knowledge import KnowledgeAnswerResult
from travelx_agent.domain.message_decision import MessageDecision
from travelx_agent.domain.policy_decision import PolicyDecision
from travelx_agent.domain.ticket_draft import TicketEditResult, TicketFeatureDecision
from travelx_agent.domain.department_agent import DepartmentAgentResult

class CustomerWorkflowState(TypedDict):
    message: str
    requested_draft_version: NotRequired[int | None]
    conversation: ConversationState
    ingress_policy: NotRequired[PolicyDecision]
    semantic_policy: NotRequired[PolicyDecision]
    raw_classification: NotRequired[MessageDecision]
    classification: NotRequired[MessageDecision]
    requirement_collection: NotRequired[RequirementCollectionResult]
    business_policy: NotRequired[PolicyDecision]
    feature_decision: NotRequired[TicketFeatureDecision]
    ticket_edit_result: NotRequired[TicketEditResult]
    ticket_confirmation_result: NotRequired[TicketConfirmationResult]
    knowledge_answer: NotRequired[KnowledgeAnswerResult]
    assistant_response: NotRequired[AssistantResponse]
    department_agent_result: NotRequired[DepartmentAgentResult]