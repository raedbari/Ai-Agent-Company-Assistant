import json
import re
from datetime import UTC, datetime

from travelx_agent.core.config import Settings
from travelx_agent.domain.conversation_state import ConversationState
from travelx_agent.domain.message_decision import MessageDecision, MessageIntent
from travelx_agent.domain.policy_decision import PolicyAction, PolicyDecision


_MESSAGE_SEPARATORS = re.compile(r"[\W_]+", re.UNICODE)


def _normalize_message(message: str) -> str:
    normalized = message.casefold()
    normalized = normalized.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    normalized = normalized.replace("ى", "ي")
    return " ".join(_MESSAGE_SEPARATORS.sub(" ", normalized).split())


def track_message_repetition(
    state: ConversationState,
    message: str,
    now: datetime | None = None,
) -> ConversationState:
    """Track exact wording without treating content repetition as a rate limit."""
    updated = state.model_copy(deep=True)
    current = _normalize_message(message)
    previous = _normalize_message(state.last_user_message or "")

    if current and previous and current == previous:
        updated.counters.exact_repeat_count += 1
    else:
        updated.counters.exact_repeat_count = 0

    # Request velocity is enforced by TrafficGuard (Redis or memory) at the API
    # boundary. Keeping a second content-based "rapid" counter here caused
    # genuine customers who needed clarification to be treated as attackers.
    updated.counters.rapid_repeat_count = 0
    updated.updated_at = now or datetime.now(UTC)
    return updated


def _build_semantic_signature(
    state: ConversationState,
    decision: MessageDecision,
) -> str:
    candidates = sorted(
        decision.service_candidates,
        key=lambda candidate: candidate.confidence,
        reverse=True,
    )
    service_key = (
        candidates[0].service_key.value
        if candidates
        else state.current_service.value
        if state.current_service
        else "none"
    )
    is_pricing = (
        decision.pricing_requested
        or decision.primary_intent is MessageIntent.PRICE_INQUIRY
    )
    payload = {
        "family": "pricing" if is_pricing else decision.primary_intent.value,
        "service": service_key,
        "goal": "" if is_pricing else _normalize_message(decision.user_goal),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _same_semantic_signature(current: str, previous: str | None) -> bool:
    if not previous:
        return False
    try:
        current_data = json.loads(current)
        previous_data = json.loads(previous)
    except (json.JSONDecodeError, TypeError):
        return current == previous

    if current_data["family"] != previous_data.get("family"):
        return False
    if current_data["service"] != previous_data.get("service"):
        return False
    if current_data["family"] == "pricing":
        return True

    current_tokens = set(current_data["goal"].split())
    previous_tokens = set(str(previous_data.get("goal", "")).split())
    if not current_tokens or not previous_tokens:
        return current_data["goal"] == previous_data.get("goal")

    overlap = len(current_tokens & previous_tokens) / min(
        len(current_tokens),
        len(previous_tokens),
    )
    return overlap >= 0.6


def track_semantic_repetition(
    state: ConversationState,
    decision: MessageDecision,
    now: datetime | None = None,
) -> ConversationState:
    """Track dialogue repetition and real clarification failures separately."""
    updated = state.model_copy(deep=True)
    signature = _build_semantic_signature(updated, decision)
    has_meaningful_progress = bool(decision.extracted_requirements) or (
        decision.primary_intent
        in {
            MessageIntent.TICKET_EDIT,
            MessageIntent.TICKET_CONFIRM,
        }
    )
    is_confusion_without_progress = (
        decision.primary_intent is MessageIntent.CLARIFICATION
        and not decision.extracted_requirements
    )

    is_same_goal = _same_semantic_signature(
        signature,
        updated.last_semantic_signature,
    )

    if has_meaningful_progress:
        updated.counters.semantic_repeat_count = 0
        updated.counters.clarification_attempts = 0
    elif is_same_goal:
        updated.counters.semantic_repeat_count += 1
    else:
        updated.counters.semantic_repeat_count = 0

    if has_meaningful_progress:
        updated.counters.clarification_attempts = 0
    elif is_confusion_without_progress:
        updated.counters.clarification_attempts += 1
    else:
        updated.counters.clarification_attempts = 0

    # TrafficGuard owns request-rate protection. This counter is cleared so
    # persisted sessions from the former mixed policy cannot remain trapped.
    updated.counters.rapid_repeat_count = 0
    updated.last_semantic_signature = signature
    updated.updated_at = now or datetime.now(UTC)
    return updated


def evaluate_semantic_policy(
    state: ConversationState,
    settings: Settings,
) -> PolicyDecision:
    """Semantic repetition is a dialogue signal, never a security violation."""
    del state, settings
    return PolicyDecision(
        action=PolicyAction.CONTINUE,
        allow_model_call=True,
        allow_freeform_response=True,
        allow_ticket_creation=False,
        reason_code="semantic_repetition_delegated_to_dialogue_policy",
    )


def evaluate_ingress_policy(
    state: ConversationState,
    settings: Settings,
    now: datetime | None = None,
) -> PolicyDecision:
    """Honor an active suspension; API TrafficGuard handles new violations."""
    del settings
    current_time = now or datetime.now(UTC)

    if state.suspended_until and state.suspended_until > current_time:
        return PolicyDecision(
            action=PolicyAction.TEMPORARILY_SUSPEND,
            allow_model_call=False,
            allow_freeform_response=False,
            allow_ticket_creation=False,
            reason_code="session_already_suspended",
            response_key="session_temporarily_suspended",
        )

    return PolicyDecision(
        action=PolicyAction.CONTINUE,
        allow_model_call=True,
        allow_freeform_response=True,
        allow_ticket_creation=False,
        reason_code="ingress_allowed",
    )


def evaluate_business_policy(
    state: ConversationState,
    decision: MessageDecision,
    settings: Settings,
) -> PolicyDecision:
    if decision.pricing_requested:
        return PolicyDecision(
            action=PolicyAction.APPLY_PRICING_POLICY,
            allow_model_call=True,
            allow_freeform_response=False,
            allow_ticket_creation=False,
            reason_code="pricing_must_be_set_by_department",
            response_key="pricing_requires_department_review",
        )

    is_confusion_without_progress = (
        decision.primary_intent is MessageIntent.CLARIFICATION
        and not decision.extracted_requirements
    )

    if (
        is_confusion_without_progress
        and state.counters.clarification_attempts
        >= settings.clarification_handoff_threshold
    ):
        return PolicyDecision(
            action=PolicyAction.OFFER_HUMAN_HANDOFF,
            allow_model_call=False,
            allow_freeform_response=False,
            allow_ticket_creation=False,
            reason_code="clarification_attempts_exhausted",
            response_key="offer_human_handoff",
        )

    if is_confusion_without_progress or state.counters.semantic_repeat_count >= 1:
        return PolicyDecision(
            action=PolicyAction.EXPLAIN_DIFFERENTLY,
            allow_model_call=True,
            allow_freeform_response=True,
            allow_ticket_creation=False,
            reason_code=(
                "customer_requested_simpler_explanation"
                if is_confusion_without_progress
                else "semantic_question_repeated"
            ),
        )

    return PolicyDecision(
        action=PolicyAction.CONTINUE,
        allow_model_call=True,
        allow_freeform_response=True,
        allow_ticket_creation=False,
        reason_code="business_flow_allowed",
    )
