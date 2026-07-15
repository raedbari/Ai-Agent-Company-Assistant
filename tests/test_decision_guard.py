from travelx_agent.application.decision_guard import guard_message_decision
from travelx_agent.domain.conversation_state import ConversationStage, ConversationState
from travelx_agent.domain.message_decision import (
    ExtractedRequirement,
    MessageDecision,
    MessageIntent,
)
from travelx_agent.domain.service_catalog import Department, ServiceKey
from travelx_agent.domain.ticket_draft import TicketDraft


def make_follow_up_conversation() -> ConversationState:
    return ConversationState(
        session_id="session-1",
        stage=ConversationStage.REQUIREMENTS,
        current_service=ServiceKey.WEBSITE_DEVELOPMENT,
        last_question_key="website_goal",
        last_question_text="ما الهدف الأساسي من الموقع؟",
    )


def test_guard_removes_unsupported_fields_and_carried_pricing() -> None:
    decision = MessageDecision(
        primary_intent=MessageIntent.CLARIFICATION,
        secondary_intents=[MessageIntent.PRICE_INQUIRY],
        user_goal="توضيح هدف الموقع",
        extracted_requirements=[
            ExtractedRequirement(
                key="website_goal",
                value="عرض قائمة الطعام واستقبال الطلبات",
                evidence="عرض قائمة الطعام واستقبال الطلبات",
            ),
            ExtractedRequirement(key="existing_website", value="no"),
        ],
        pricing_requested=True,
        has_existing_system=False,
        confidence=0.94,
    )

    result = guard_message_decision(
        make_follow_up_conversation(),
        decision,
        "الهدف عرض قائمة الطعام واستقبال الطلبات",
    )

    assert [item.key for item in result.extracted_requirements] == ["website_goal"]
    assert result.has_existing_system is None
    assert result.pricing_requested is False
    assert MessageIntent.PRICE_INQUIRY not in result.secondary_intents


def test_guard_keeps_extra_field_only_with_current_message_evidence() -> None:
    decision = MessageDecision(
        primary_intent=MessageIntent.CLARIFICATION,
        user_goal="توضيح الهدف وميزة إضافية",
        extracted_requirements=[
            ExtractedRequirement(
                key="website_goal",
                value="عرض المطعم",
                evidence="عرض المطعم",
            ),
            ExtractedRequirement(
                key="features",
                value="الدفع الإلكتروني",
                evidence="الدفع الإلكتروني",
            ),
        ],
        confidence=0.95,
    )

    result = guard_message_decision(
        make_follow_up_conversation(),
        decision,
        "الهدف عرض المطعم وأريد الدفع الإلكتروني",
    )

    assert [item.key for item in result.extracted_requirements] == [
        "website_goal",
        "features",
    ]


def test_guard_detects_explicit_price_request_in_current_message() -> None:
    decision = MessageDecision(
        primary_intent=MessageIntent.SERVICE_REQUEST,
        user_goal="إنشاء موقع",
        pricing_requested=False,
        confidence=0.9,
    )

    result = guard_message_decision(
        ConversationState(session_id="session-1"),
        decision,
        "أريد موقعًا، كم بيكلف؟",
    )

    assert result.pricing_requested is True
    assert MessageIntent.PRICE_INQUIRY in result.secondary_intents


def test_guard_treats_desired_capability_as_edit_during_draft_review() -> None:
    conversation = ConversationState(
        session_id="draft-session",
        stage=ConversationStage.DRAFT_REVIEW,
        current_service=ServiceKey.AI_AGENT,
        ticket_draft=TicketDraft(
            service_key=ServiceKey.AI_AGENT,
            primary_department=Department.CYBTX,
        ),
    )
    decision = MessageDecision(
        primary_intent=MessageIntent.SERVICE_REQUEST,
        user_goal="تحسين استهلاك الرموز",
        confidence=0.92,
    )

    result = guard_message_decision(
        conversation,
        decision,
        "أريده ألا يستهلك الرموز بشكل غير ضروري",
    )

    assert result.primary_intent is MessageIntent.TICKET_EDIT