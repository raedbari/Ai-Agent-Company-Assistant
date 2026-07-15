from travelx_agent.application.requirements_collector import collect_requirements
from travelx_agent.domain.conversation_state import (
    ConversationStage,
    ConversationState,
)
from travelx_agent.domain.message_decision import MessageDecision
from travelx_agent.prompts.message_classifier import MESSAGE_CLASSIFIER_PROMPT


MESSAGE = (
    "أريد موقعًا جديدًا لمطعم، هدفه عرض قائمة الطعام واستقبال الطلبات، "
    "لا يوجد لدي موقع حالي، أحتاج الطلبات والحجوزات، "
    "واللغات العربية والإنجليزية."
)


def test_compound_website_request_preserves_explicit_goal() -> None:
    decision = MessageDecision.model_validate(
        {
            "primary_intent": "service_request",
            "user_goal": "إنشاء موقع لمطعم",
            "service_candidates": [
                {
                    "service_key": "website_development",
                    "confidence": 0.98,
                }
            ],
            "extracted_requirements": [
                {
                    "key": "business_type",
                    "value": "مطعم",
                    "evidence": "لمطعم",
                },
                {
                    "key": "website_goal",
                    "value": "عرض قائمة الطعام واستقبال الطلبات",
                    "evidence": "هدفه عرض قائمة الطعام واستقبال الطلبات",
                },
                {
                    "key": "features",
                    "value": "الطلبات والحجوزات",
                    "evidence": "أحتاج الطلبات والحجوزات",
                },
                {
                    "key": "languages",
                    "value": "العربية والإنجليزية",
                    "evidence": "اللغات العربية والإنجليزية",
                },
            ],
            "has_existing_system": False,
            "has_existing_system_evidence": "لا يوجد لدي موقع حالي",
            "confidence": 0.95,
        }
    )

    result = collect_requirements(
        ConversationState(session_id="website-goal-test"),
        decision,
        MESSAGE,
    )

    assert result.conversation.collected_requirements["website_goal"] == (
        "عرض قائمة الطعام واستقبال الطلبات"
    )
    assert result.conversation.missing_requirements == []
    assert result.conversation.stage is ConversationStage.DRAFT_REVIEW


def test_classifier_prompt_requires_compound_goal_extraction() -> None:
    messages = MESSAGE_CLASSIFIER_PROMPT.format_messages(
        catalog_context="test catalog",
        format_instructions="test schema",
        conversation_context="no previous context",
        message=MESSAGE,
        validation_feedback="No previous attempt.",
    )

    system_prompt = str(messages[0].content)

    assert "website_goal" in system_prompt
    assert "هدفه" in system_prompt
    assert "do not stop after finding only some" in system_prompt