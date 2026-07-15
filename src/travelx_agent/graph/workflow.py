import json
from datetime import UTC, datetime, timedelta

from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from travelx_agent.application.decision_guard import guard_message_decision
from travelx_agent.application.department_agent import DepartmentAgentRegistry
from travelx_agent.application.knowledge_answerer import answer_from_knowledge
from travelx_agent.application.message_classifier import classify_message
from travelx_agent.application.policy_engine import (
    evaluate_business_policy,
    evaluate_ingress_policy,
    evaluate_semantic_policy,
    track_message_repetition,
    track_semantic_repetition,
)
from travelx_agent.application.ports.ticket_repository import TicketRepository
from travelx_agent.application.requirements_collector import collect_requirements
from travelx_agent.application.response_builder import (
    build_blocked_response,
    build_business_response,
    build_knowledge_response,
    build_ticket_edit_response,
)
from travelx_agent.application.ticket_confirmation_response import (
    build_ticket_confirmation_response,
)
from travelx_agent.application.ticket_creation_service import confirm_and_create_ticket
from travelx_agent.application.ticket_draft_service import (
    apply_ticket_edit,
    build_ticket_draft,
)
from travelx_agent.application.ticket_feature_validator import validate_ticket_feature
from travelx_agent.core.config import Settings
from travelx_agent.domain.conversation_state import ConversationStage, ConversationState
from travelx_agent.domain.department_agent import DepartmentAgentRequest
from travelx_agent.domain.knowledge import KnowledgeAnswerResult, KnowledgeSource
from travelx_agent.domain.message_decision import MessageIntent
from travelx_agent.domain.policy_decision import PolicyAction
from travelx_agent.domain.service_catalog import get_service
from travelx_agent.domain.ticket_draft import (
    FeatureDecisionAction,
    TicketFeatureDecision,
)
from travelx_agent.graph.state import CustomerWorkflowState
from travelx_agent.infrastructure.knowledge_base import TravelXKnowledgeBase


def _build_conversation_context(conversation: ConversationState) -> str:
    service = get_service(conversation.current_service)
    active_requirement = (
        next(
            (
                item
                for item in service.requirements
                if item.key == conversation.last_question_key
            ),
            None,
        )
        if service and conversation.last_question_key
        else None
    )
    context = {
        "stage": conversation.stage.value,
        "current_service": (
            conversation.current_service.value if conversation.current_service else None
        ),
        "collected_requirement_keys": list(conversation.collected_requirements),
        "missing_requirements": conversation.missing_requirements,
        "repeat_context": {
            "exact_repeat_count": conversation.counters.exact_repeat_count,
            "semantic_repeat_count": conversation.counters.semantic_repeat_count,
            "clarification_attempts": conversation.counters.clarification_attempts,
            "previous_assistant_response": conversation.last_assistant_response,
        },
        "active_requirement": (
            {
                "key": active_requirement.key,
                "label_ar": active_requirement.label_ar,
                "question_ar": active_requirement.question_ar,
                "value_kind": active_requirement.value_kind.value,
            }
            if active_requirement
            else None
        ),
        "ticket_draft": (
            {
                "exists": True,
                "version": conversation.ticket_draft.version,
                "status": conversation.ticket_draft.status.value,
            }
            if conversation.ticket_draft
            else {"exists": False}
        ),
        "created_ticket_number": (
            conversation.created_ticket.ticket_number
            if conversation.created_ticket
            else None
        ),
    }
    return json.dumps(context, ensure_ascii=False)


def build_customer_workflow(
    classifier: Runnable,
    settings: Settings,
    feature_validator: Runnable | None = None,
    ticket_repository: TicketRepository | None = None,
    knowledge_answerer: Runnable | None = None,
    knowledge_base: TravelXKnowledgeBase | None = None,
    department_agents: DepartmentAgentRegistry | None = None,
) -> CompiledStateGraph:
    def check_ingress_policy(state: CustomerWorkflowState) -> dict:
        now = datetime.now(UTC)
        conversation = track_message_repetition(
            state["conversation"],
            state["message"],
            now,
        )
        decision = evaluate_ingress_policy(conversation, settings, now)
        if decision.action is PolicyAction.TEMPORARILY_SUSPEND:
            conversation.suspended_until = now + timedelta(
                seconds=settings.temporary_suspension_seconds
            )
            conversation.stage = ConversationStage.SUSPENDED
        return {"conversation": conversation, "ingress_policy": decision}

    def route_after_ingress(state: CustomerWorkflowState) -> str:
        if state["ingress_policy"].action is PolicyAction.CONTINUE:
            return "classify"
        return "stop"

    async def classify_customer_message(state: CustomerWorkflowState) -> dict:
        raw_decision = await classify_message(
            classifier,
            state["message"],
            _build_conversation_context(state["conversation"]),
        )
        guarded_decision = guard_message_decision(
            state["conversation"],
            raw_decision,
            state["message"],
        )
        now = datetime.now(UTC)
        conversation = track_semantic_repetition(
            state["conversation"],
            guarded_decision,
            now,
        )
        semantic_policy = evaluate_semantic_policy(conversation, settings)
        if semantic_policy.action is PolicyAction.TEMPORARILY_SUSPEND:
            conversation.suspended_until = now + timedelta(
                seconds=settings.temporary_suspension_seconds
            )
            conversation.stage = ConversationStage.SUSPENDED
        return {
            "conversation": conversation,
            "raw_classification": raw_decision,
            "classification": guarded_decision,
            "semantic_policy": semantic_policy,
        }

    def route_after_classification(state: CustomerWorkflowState) -> str:
        semantic_policy = state.get("semantic_policy")
        if (
            semantic_policy is not None
            and semantic_policy.action is not PolicyAction.CONTINUE
        ):
            return "blocked"
        conversation = state["conversation"]
        intent = state["classification"].primary_intent
        if intent is MessageIntent.TICKET_CONFIRM and conversation.ticket_draft is not None:
            return "ticket_confirm"
        if (
            intent is MessageIntent.TICKET_EDIT
            and conversation.stage is ConversationStage.DRAFT_REVIEW
            and conversation.ticket_draft is not None
        ):
            return "ticket_edit"
        if intent in {
            MessageIntent.SERVICE_QUESTION,
            MessageIntent.PRICE_INQUIRY,
        }:
            return "knowledge"
        return "requirements"

    async def answer_knowledge_question(state: CustomerWorkflowState) -> dict:
        conversation = state["conversation"].model_copy(deep=True)
        decision = state["classification"]
        candidates = sorted(
            decision.service_candidates,
            key=lambda candidate: candidate.confidence,
            reverse=True,
        )
        service = get_service(candidates[0].service_key) if candidates else None
        service = service or get_service(conversation.current_service)
        policy = evaluate_business_policy(conversation, decision, settings)
        department_agent_result = None

        if decision.primary_intent is MessageIntent.PRICE_INQUIRY:
            repeat_count = conversation.counters.semantic_repeat_count
            if repeat_count == 0:
                pricing_text = (
                    "يحدد القسم المختص التكلفة بعد مراجعة المتطلبات، "
                    "ولا يقدم النظام سعرًا نهائيًا. يمكنني جمع متطلبات الخدمة "
                    "وتجهيز تذكرة للقسم المختص."
                )
            elif repeat_count == 1:
                pricing_text = (
                    "بصياغة أبسط: لا يوجد سعر آلي أو ثابت داخل المحادثة؛ "
                    "تختلف التكلفة حسب المتطلبات ويحددها القسم المختص بعد المراجعة. "
                    "هل تريد أن نبدأ بجمع المتطلبات؟"
                )
            else:
                pricing_text = (
                    "سياسة السعر لم تتغير: لا يستطيع الموظف الرقمي تحديد التكلفة. "
                    "يحددها القسم المختص بعد معرفة المتطلبات."
                )
            policy_sources = (
                [
                    KnowledgeSource(
                        source_id="travelx-customer-service-policies",
                        title_ar="سياسات خدمة العملاء والتذاكر",
                    )
                ]
                if knowledge_base is not None
                else []
            )
            knowledge_result = KnowledgeAnswerResult(
                text=pricing_text,
                sources=policy_sources,
                sufficient_context=True,
            )
        elif policy.action is PolicyAction.OFFER_HUMAN_HANDOFF:
            knowledge_result = KnowledgeAnswerResult(
                text="لم نصل إلى إجابة واضحة بعد عدة محاولات. هل تريد التحدث مع موظف؟",
                sufficient_context=False,
            )
        elif service is not None and department_agents is not None:
            request = DepartmentAgentRequest(
                question=state["message"],
                service_key=service.key,
                previous_answer=conversation.last_assistant_response,
                explain_differently=(
                    policy.action is PolicyAction.EXPLAIN_DIFFERENTLY
                    or conversation.counters.exact_repeat_count >= 1
                ),
            )
            department_agent = department_agents.get(
                service.primary_department
            )
            department_agent_result = await department_agent.run(request)
            knowledge_result = department_agent_result.knowledge
        elif knowledge_answerer is None or knowledge_base is None:
            knowledge_result = KnowledgeAnswerResult(
                text=(
                    "لا تتوفر لدي معلومات موثقة كافية للإجابة عن هذا السؤال. "
                    "يمكنني تجهيز طلب للقسم المختص."
                ),
                sufficient_context=False,
            )
        else:
            knowledge_result = await answer_from_knowledge(
                knowledge_answerer,
                knowledge_base,
                state["message"],
                service.key if service else None,
                limit=settings.knowledge_top_k,
                previous_answer=conversation.last_assistant_response,
                explain_differently=(
                    policy.action is PolicyAction.EXPLAIN_DIFFERENTLY
                    or conversation.counters.exact_repeat_count >= 1
                ),
            )

        text = knowledge_result.text
        if (
            policy.action is PolicyAction.APPLY_PRICING_POLICY
            and decision.primary_intent is not MessageIntent.PRICE_INQUIRY
        ):
            pricing_notice = (
                "يحدد القسم المختص التكلفة بعد مراجعة المتطلبات، "
                "ولا يقدم النظام سعرًا نهائيًا."
            )
            if pricing_notice not in text:
                text = f"{pricing_notice} {text}"

        if service and conversation.current_service is None:
            conversation.current_service = service.key
        if conversation.stage is ConversationStage.NEW:
            conversation.stage = ConversationStage.DISCOVERY
        conversation.last_user_message = state["message"]
        conversation.last_assistant_response = text
        conversation.updated_at = datetime.now(UTC)

        response = build_knowledge_response(
            text=text,
            policy_action=policy.action,
            stage=conversation.stage,
            service=service,
            sources=knowledge_result.sources,
            missing_requirements=[],
        )
        updates = {
            "conversation": conversation,
            "business_policy": policy,
            "knowledge_answer": knowledge_result,
            "assistant_response": response,
        }
        if department_agent_result is not None:
            updates["department_agent_result"] = department_agent_result
        return updates

    def collect_customer_requirements(state: CustomerWorkflowState) -> dict:
        collection = collect_requirements(
            state["conversation"],
            state["classification"],
            state["message"],
        )
        conversation = collection.conversation
        if conversation.stage is ConversationStage.DRAFT_REVIEW:
            conversation.ticket_draft = build_ticket_draft(conversation)
        return {
            "conversation": conversation,
            "requirement_collection": collection,
        }

    def apply_business_policy(state: CustomerWorkflowState) -> dict:
        decision = evaluate_business_policy(
            state["conversation"],
            state["classification"],
            settings,
        )
        return {"business_policy": decision}

    async def validate_draft_edit(state: CustomerWorkflowState) -> dict:
        draft = state["conversation"].ticket_draft
        if draft is None:
            raise ValueError("A ticket draft is required before validating an edit")
        if feature_validator is None:
            decision = TicketFeatureDecision(
                action=FeatureDecisionAction.CLARIFY,
                edits=[],
                reason_code="feature_validator_not_configured",
                clarification_question_ar="وضح الميزة التي تريد تعديلها.",
                confidence=0.0,
            )
        else:
            decision = await validate_ticket_feature(
                feature_validator,
                draft,
                state["message"],
            )
        return {"feature_decision": decision}

    def apply_draft_edit(state: CustomerWorkflowState) -> dict:
        conversation = state["conversation"].model_copy(deep=True)
        if conversation.ticket_draft is None:
            raise ValueError("A ticket draft is required before applying an edit")
        edit_result = apply_ticket_edit(
            conversation.ticket_draft,
            state["feature_decision"],
        )
        conversation.ticket_draft = edit_result.draft
        conversation.last_user_message = state["message"]
        conversation.updated_at = datetime.now(UTC)
        return {
            "conversation": conversation,
            "ticket_edit_result": edit_result,
        }

    async def confirm_ticket(state: CustomerWorkflowState) -> dict:
        if ticket_repository is None:
            raise RuntimeError("Ticket repository is not configured")
        result = await confirm_and_create_ticket(
            state["conversation"],
            state.get("requested_draft_version"),
            ticket_repository,
        )
        return {
            "conversation": result.conversation,
            "ticket_confirmation_result": result,
        }

    def respond_to_blocked_request(state: CustomerWorkflowState) -> dict:
        conversation = state["conversation"].model_copy(deep=True)
        policy = state.get("semantic_policy", state["ingress_policy"])
        response = build_blocked_response(
            policy,
            conversation.stage,
        )
        conversation.last_user_message = state["message"]
        conversation.last_assistant_response = response.text
        conversation.updated_at = datetime.now(UTC)
        return {"conversation": conversation, "assistant_response": response}

    def respond_to_customer(state: CustomerWorkflowState) -> dict:
        response = build_business_response(
            state["classification"],
            state["business_policy"],
            state["requirement_collection"],
        )
        return {
            "conversation": state["requirement_collection"].conversation,
            "assistant_response": response,
        }

    def respond_to_ticket_edit(state: CustomerWorkflowState) -> dict:
        response = build_ticket_edit_response(
            state["feature_decision"],
            state["ticket_edit_result"],
            state["conversation"],
        )
        return {
            "conversation": state["conversation"],
            "assistant_response": response,
        }

    def respond_to_ticket_confirmation(state: CustomerWorkflowState) -> dict:
        response = build_ticket_confirmation_response(
            state["ticket_confirmation_result"]
        )
        return {
            "conversation": state["ticket_confirmation_result"].conversation,
            "assistant_response": response,
        }

    graph = StateGraph(CustomerWorkflowState)
    graph.add_node("check_ingress_policy", check_ingress_policy)
    graph.add_node("classify_message", classify_customer_message)
    graph.add_node("collect_requirements", collect_customer_requirements)
    graph.add_node("answer_knowledge", answer_knowledge_question)
    graph.add_node("apply_business_policy", apply_business_policy)
    graph.add_node("validate_draft_edit", validate_draft_edit)
    graph.add_node("apply_draft_edit", apply_draft_edit)
    graph.add_node("confirm_ticket", confirm_ticket)
    graph.add_node("blocked_response", respond_to_blocked_request)
    graph.add_node("customer_response", respond_to_customer)
    graph.add_node("ticket_edit_response", respond_to_ticket_edit)
    graph.add_node("ticket_confirmation_response", respond_to_ticket_confirmation)

    graph.add_edge(START, "check_ingress_policy")
    graph.add_conditional_edges(
        "check_ingress_policy",
        route_after_ingress,
        {"classify": "classify_message", "stop": "blocked_response"},
    )
    graph.add_conditional_edges(
        "classify_message",
        route_after_classification,
        {
            "blocked": "blocked_response",
            "ticket_confirm": "confirm_ticket",
            "ticket_edit": "validate_draft_edit",
            "knowledge": "answer_knowledge",
            "requirements": "collect_requirements",
        },
    )
    graph.add_edge("collect_requirements", "apply_business_policy")
    graph.add_edge("apply_business_policy", "customer_response")
    graph.add_edge("validate_draft_edit", "apply_draft_edit")
    graph.add_edge("apply_draft_edit", "ticket_edit_response")
    graph.add_edge("confirm_ticket", "ticket_confirmation_response")
    graph.add_edge("blocked_response", END)
    graph.add_edge("customer_response", END)
    graph.add_edge("ticket_edit_response", END)
    graph.add_edge("ticket_confirmation_response", END)
    graph.add_edge("answer_knowledge", END)

    return graph.compile()