from datetime import UTC, datetime, timedelta

from travelx_agent.application.policy_engine import (
    evaluate_business_policy,
    evaluate_ingress_policy,
    evaluate_semantic_policy,
    track_message_repetition,
    track_semantic_repetition,
)
from travelx_agent.core.config import Settings
from travelx_agent.domain.conversation_state import (
    ConversationCounters,
    ConversationState,
)
from travelx_agent.domain.message_decision import (
    ExtractedRequirement,
    MessageDecision,
    MessageIntent,
    ServiceCandidate,
)
from travelx_agent.domain.policy_decision import PolicyAction
from travelx_agent.domain.service_catalog import ServiceKey


def make_decision(
    *,
    intent: MessageIntent = MessageIntent.SERVICE_REQUEST,
    pricing_requested: bool = False,
) -> MessageDecision:
    return MessageDecision(
        primary_intent=intent,
        user_goal="طلب خدمة",
        pricing_requested=pricing_requested,
        confidence=0.9,
    )


def test_active_suspension_blocks_model_call() -> None:
    now = datetime.now(UTC)
    state = ConversationState(
        session_id="session-1",
        suspended_until=now + timedelta(minutes=10),
    )

    result = evaluate_ingress_policy(state, Settings(), now=now)

    assert result.action is PolicyAction.TEMPORARILY_SUSPEND
    assert result.allow_model_call is False


def test_content_counters_do_not_create_fake_human_check() -> None:
    state = ConversationState(
        session_id="session-1",
        counters=ConversationCounters(
            exact_repeat_count=8,
            semantic_repeat_count=8,
            rapid_repeat_count=8,
        ),
    )

    result = evaluate_ingress_policy(state, Settings())

    assert result.action is PolicyAction.CONTINUE
    assert result.allow_model_call is True


def test_exact_repeat_tracks_wording_without_mixing_counters() -> None:
    state = ConversationState(
        session_id="session-1",
        last_user_message="كم تكلفة بناء AI Agent؟",
    )

    result = track_message_repetition(state, "  كم تكلفة بناء ai agent  ")

    assert result.counters.exact_repeat_count == 1
    assert result.counters.semantic_repeat_count == 0
    assert result.counters.rapid_repeat_count == 0
    assert result.counters.clarification_attempts == 0


def test_paraphrased_price_question_increments_only_semantic_counter() -> None:
    first = MessageDecision(
        primary_intent=MessageIntent.PRICE_INQUIRY,
        user_goal="معرفة تكلفة وكيل ذكاء اصطناعي",
        service_candidates=[
            ServiceCandidate(service_key=ServiceKey.AI_AGENT, confidence=0.95)
        ],
        pricing_requested=True,
        confidence=0.95,
    )
    second = first.model_copy(
        update={"user_goal": "السؤال عن سعر إنشاء AI Agent"}
    )
    state = track_semantic_repetition(
        ConversationState(session_id="semantic-repeat"),
        first,
    )

    result = track_semantic_repetition(state, second)

    assert result.counters.semantic_repeat_count == 1
    assert result.counters.rapid_repeat_count == 0
    assert result.counters.clarification_attempts == 0
    assert evaluate_semantic_policy(result, Settings()).action is PolicyAction.CONTINUE


def test_repeated_service_request_is_not_counted_as_failed_clarification() -> None:
    decision = MessageDecision(
        primary_intent=MessageIntent.SERVICE_REQUEST,
        user_goal="طلب وكيل ذكاء اصطناعي",
        service_candidates=[
            ServiceCandidate(service_key=ServiceKey.AI_AGENT, confidence=0.95)
        ],
        confidence=0.95,
    )
    state = track_semantic_repetition(
        ConversationState(session_id="agent-repeat"),
        decision,
    )

    result = track_semantic_repetition(state, decision)

    assert result.counters.semantic_repeat_count == 1
    assert result.counters.clarification_attempts == 0


def test_explicit_confusion_increments_clarification_attempts() -> None:
    decision = MessageDecision(
        primary_intent=MessageIntent.CLARIFICATION,
        user_goal="طلب شرح أبسط للسؤال الحالي",
        confidence=0.95,
    )

    result = track_semantic_repetition(
        ConversationState(session_id="confused-customer"),
        decision,
    )

    assert result.counters.clarification_attempts == 1
    assert (
        evaluate_business_policy(result, decision, Settings()).action
        is PolicyAction.EXPLAIN_DIFFERENTLY
    )


def test_new_requirement_resets_dialogue_counters() -> None:
    state = ConversationState(
        session_id="requirements-progress",
        counters=ConversationCounters(
            semantic_repeat_count=2,
            rapid_repeat_count=3,
            clarification_attempts=2,
        ),
    )
    decision = MessageDecision(
        primary_intent=MessageIntent.CLARIFICATION,
        user_goal="إضافة متطلب حماية",
        extracted_requirements=[
            ExtractedRequirement(
                key="features",
                value="حماية من الهجمات",
                evidence="حماية من الهجمات",
            )
        ],
        confidence=0.94,
    )

    result = track_semantic_repetition(state, decision)

    assert result.counters.semantic_repeat_count == 0
    assert result.counters.rapid_repeat_count == 0
    assert result.counters.clarification_attempts == 0


def test_pricing_question_uses_controlled_response_policy() -> None:
    state = ConversationState(session_id="session-1")

    result = evaluate_business_policy(
        state,
        make_decision(pricing_requested=True),
        Settings(),
    )

    assert result.action is PolicyAction.APPLY_PRICING_POLICY
    assert result.allow_freeform_response is False


def test_repeated_request_is_sent_for_different_explanation() -> None:
    state = ConversationState(
        session_id="session-1",
        counters=ConversationCounters(semantic_repeat_count=1),
    )

    result = evaluate_business_policy(state, make_decision(), Settings())

    assert result.action is PolicyAction.EXPLAIN_DIFFERENTLY
    assert result.allow_model_call is True


def test_failed_real_clarifications_offer_handoff() -> None:
    state = ConversationState(
        session_id="session-1",
        counters=ConversationCounters(clarification_attempts=3),
    )
    decision = make_decision(intent=MessageIntent.CLARIFICATION)

    result = evaluate_business_policy(state, decision, Settings())

    assert result.action is PolicyAction.OFFER_HUMAN_HANDOFF
    assert result.allow_model_call is False
