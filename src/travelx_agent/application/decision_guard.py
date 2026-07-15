import re

from travelx_agent.domain.conversation_state import (
    ConversationStage,
    ConversationState,
)
from travelx_agent.domain.message_decision import MessageDecision, MessageIntent


_ARABIC_DIACRITICS = re.compile(r"[\u0617-\u061A\u064B-\u0652]")
_TEXT_SEPARATORS = re.compile(r"[\W_]+", re.UNICODE)
_PRICE_SIGNALS = (
    "سعر",
    "تكلف",
    "بكم",
    "كم يكلف",
    "كم بيكلف",
    "ميزاني",
    "price",
    "cost",
)
_CONFUSION_SIGNALS = (
    "مافهم",
    "لمافهم",
    "مافهمت",
    "مافهمتك",
    "مشفاهم",
    "مانيفاهم",
    "غيرواضح",
    "غيرمفهوم",
    "مشواضح",
    "موواضح",
    "ماكانواضح",
)
_CONTEXTUAL_CLARIFICATION_SIGNALS = (
    "وضحها",
    "اشرحها",
    "بسطها",
    "وضحلي",
    "فهمني",
    "ماذاتقصد",
    "وشتقصد",
    "ايشتقصد",
    "ماالمقصود",
)
_IDENTITY_SIGNALS = (
    "مااسمك",
    "وشاسمك",
    "ايشاسمك",
    "اسمكايه",
    "منانت",
    "مينانت",
    "منتكون",
    "عرفنفسك",
    "عرفنيبنفسك",
)
_SOCIAL_GREETING_SIGNALS = (
    "كيفحالك",
    "كيفك",
    "شلونك",
    "اخبارك",
)
_DRAFT_EDIT_SIGNALS = (
    "اضف",
    "احذف",
    "ازل",
    "عدل",
    "استبدل",
    "غيرالميزه",
    "اريدايضا",
    "اريده",
    "لااريد",
)


def _normalize_text(value: str) -> str:
    normalized = _ARABIC_DIACRITICS.sub("", value.casefold())
    normalized = normalized.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    normalized = normalized.replace("ى", "ي")
    normalized = _TEXT_SEPARATORS.sub(" ", normalized)
    return " ".join(normalized.split())


def _compact_text(value: str) -> str:
    return _normalize_text(value).replace(" ", "")


def _evidence_exists(evidence: str | None, message: str) -> bool:
    if not evidence:
        return False
    normalized_evidence = _normalize_text(evidence)
    normalized_message = _normalize_text(message)
    return len(normalized_evidence) >= 2 and normalized_evidence in normalized_message


def _message_requests_pricing(decision: MessageDecision, message: str) -> bool:
    if _evidence_exists(decision.pricing_evidence, message):
        return True
    normalized_message = _normalize_text(message)
    return any(signal in normalized_message for signal in _PRICE_SIGNALS)


def _message_expresses_confusion(
    conversation: ConversationState,
    message: str,
) -> bool:
    compact = _compact_text(message)
    if any(signal in compact for signal in _CONFUSION_SIGNALS):
        return True

    has_active_question = bool(
        conversation.last_question_key
        or conversation.last_question_text
        or conversation.last_assistant_response
    )
    return has_active_question and any(
        signal in compact for signal in _CONTEXTUAL_CLARIFICATION_SIGNALS
    )


def _looks_like_draft_edit(message: str) -> bool:
    compact = _compact_text(message)
    return any(signal in compact for signal in _DRAFT_EDIT_SIGNALS)


def _message_is_identity_or_social_question(message: str) -> bool:
    compact = _compact_text(message)
    signals = (*_IDENTITY_SIGNALS, *_SOCIAL_GREETING_SIGNALS)
    return any(signal in compact for signal in signals)


def guard_message_decision(
    conversation: ConversationState,
    decision: MessageDecision,
    message: str,
) -> MessageDecision:
    """Ground model claims and deterministically repair critical dialogue intents."""

    guarded = decision.model_copy(deep=True)
    pricing_requested = _message_requests_pricing(guarded, message)
    guarded.pricing_requested = pricing_requested

    secondary_without_price = [
        intent
        for intent in guarded.secondary_intents
        if intent is not MessageIntent.PRICE_INQUIRY
    ]
    if pricing_requested:
        secondary_without_price.append(MessageIntent.PRICE_INQUIRY)
    guarded.secondary_intents = secondary_without_price

    guarded.extracted_requirements = [
        item
        for item in guarded.extracted_requirements
        if _evidence_exists(item.evidence, message)
    ]

    existing_system_has_evidence = _evidence_exists(
        guarded.has_existing_system_evidence,
        message,
    )
    if not existing_system_has_evidence:
        guarded.has_existing_system = None
        guarded.has_existing_system_evidence = None

    if not pricing_requested and _message_is_identity_or_social_question(message):
        guarded.primary_intent = MessageIntent.GREETING
        guarded.secondary_intents = []
        guarded.user_goal = "تحية أو سؤال عن هوية المساعد"
        guarded.service_candidates = []
        guarded.extracted_requirements = []
        guarded.has_existing_system = None
        guarded.has_existing_system_evidence = None
        guarded.needs_clarification = False
        guarded.confidence = max(guarded.confidence, 0.99)
        return guarded

    if _message_expresses_confusion(conversation, message):
        guarded.primary_intent = MessageIntent.CLARIFICATION
        guarded.secondary_intents = (
            [MessageIntent.PRICE_INQUIRY] if pricing_requested else []
        )
        guarded.user_goal = "طلب شرح أبسط للسؤال الحالي"
        guarded.service_candidates = []
        guarded.extracted_requirements = []
        guarded.has_existing_system = None
        guarded.has_existing_system_evidence = None
        guarded.needs_clarification = True
        guarded.confidence = max(guarded.confidence, 0.99)
        return guarded

    if (
        conversation.stage is ConversationStage.DRAFT_REVIEW
        and conversation.ticket_draft is not None
        and guarded.primary_intent
        in {
            MessageIntent.SERVICE_REQUEST,
            MessageIntent.CLARIFICATION,
            MessageIntent.UNKNOWN,
        }
        and _looks_like_draft_edit(message)
    ):
        guarded.primary_intent = MessageIntent.TICKET_EDIT

    return guarded
