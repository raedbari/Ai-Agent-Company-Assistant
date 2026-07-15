from travelx_agent.application.decision_guard import guard_message_decision
from travelx_agent.application.requirements_collector import RequirementCollectionResult
from travelx_agent.application.response_builder import (
    build_blocked_response,
    build_business_response,
)
from travelx_agent.domain.conversation_state import ConversationStage, ConversationState
from travelx_agent.domain.message_decision import MessageDecision, MessageIntent
from travelx_agent.domain.policy_decision import PolicyAction, PolicyDecision
from travelx_agent.domain.service_catalog import (
    Department,
    ServiceKey,
    get_service,
)
from travelx_agent.domain.ticket_draft import TicketDraft


def make_policy(action: PolicyAction) -> PolicyDecision:
    return PolicyDecision(
        action=action,
        allow_model_call=True,
        allow_freeform_response=True,
        allow_ticket_creation=False,
        reason_code="test",
    )


def test_guard_understands_spaced_confusion_phrase() -> None:
    conversation = ConversationState(
        session_id="confusion",
        stage=ConversationStage.REQUIREMENTS,
        current_service=ServiceKey.AI_AGENT,
        last_question_key="agent_goal",
        last_question_text="ما المهمة الأساسية التي تريد من الوكيل تنفيذها؟",
    )
    model_decision = MessageDecision(
        primary_intent=MessageIntent.UNKNOWN,
        user_goal="رسالة غير واضحة",
        confidence=0.55,
    )

    result = guard_message_decision(
        conversation,
        model_decision,
        "ما ف همت، اشرحها ببساطة",
    )

    assert result.primary_intent is MessageIntent.CLARIFICATION
    assert result.extracted_requirements == []
    assert result.service_candidates == []
    assert result.needs_clarification is True


def test_confusion_during_draft_review_is_not_changed_to_ticket_edit() -> None:
    conversation = ConversationState(
        session_id="draft-confusion",
        stage=ConversationStage.DRAFT_REVIEW,
        current_service=ServiceKey.AI_AGENT,
        last_assistant_response="راجع المسودة ثم أكدها.",
        ticket_draft=TicketDraft(
            service_key=ServiceKey.AI_AGENT,
            primary_department=Department.CYBTX,
        ),
    )
    model_decision = MessageDecision(
        primary_intent=MessageIntent.UNKNOWN,
        user_goal="عدم فهم المسودة",
        confidence=0.6,
    )

    result = guard_message_decision(
        conversation,
        model_decision,
        "لم أفهم، وضحها",
    )

    assert result.primary_intent is MessageIntent.CLARIFICATION


def test_guard_repairs_identity_question_before_workflow_routing() -> None:
    model_decision = MessageDecision(
        primary_intent=MessageIntent.SERVICE_QUESTION,
        user_goal="سؤال عام",
        confidence=0.7,
    )

    result = guard_message_decision(
        ConversationState(session_id="identity-routing"),
        model_decision,
        "ما اسمك؟",
    )

    assert result.primary_intent is MessageIntent.GREETING
    assert result.service_candidates == []


def test_identity_question_gets_identity_answer() -> None:
    conversation = ConversationState(
        session_id="identity",
        stage=ConversationStage.DISCOVERY,
        last_user_message="ما اسمك؟",
    )
    collection = RequirementCollectionResult(conversation=conversation)
    decision = MessageDecision(
        primary_intent=MessageIntent.GREETING,
        user_goal="معرفة هوية المساعد",
        confidence=0.98,
    )

    response = build_business_response(
        decision,
        make_policy(PolicyAction.CONTINUE),
        collection,
    )

    assert "مساعد Travel-X" in response.text
    assert "تجهيز التذكرة" in response.text


def test_ai_agent_confusion_uses_examples_instead_of_repeating_question() -> None:
    service = get_service(ServiceKey.AI_AGENT)
    assert service is not None
    requirement = service.requirements[0]
    conversation = ConversationState(
        session_id="agent-help",
        stage=ConversationStage.REQUIREMENTS,
        current_service=ServiceKey.AI_AGENT,
        missing_requirements=[requirement.key],
        last_user_message="لم أفهم",
    )
    collection = RequirementCollectionResult(
        conversation=conversation,
        service=service,
        next_requirement=requirement,
    )
    decision = MessageDecision(
        primary_intent=MessageIntent.CLARIFICATION,
        user_goal="طلب شرح أبسط للسؤال الحالي",
        needs_clarification=True,
        confidence=0.99,
    )

    response = build_business_response(
        decision,
        make_policy(PolicyAction.EXPLAIN_DIFFERENTLY),
        collection,
    )

    assert "الرد على العملاء" in response.text
    assert "حجز المواعيد" in response.text
    assert "ما الجزء الذي لم يكن واضحًا" not in response.text


def test_blocked_response_does_not_claim_nonexistent_human_check() -> None:
    response = build_blocked_response(
        make_policy(PolicyAction.REQUIRE_HUMAN_CHECK),
        ConversationStage.DISCOVERY,
    )

    assert "التحقق البشري" not in response.text
    assert "حماية حركة الطلبات" in response.text
