from travelx_agent.application.decision_guard import guard_message_decision
from travelx_agent.application.requirements_collector import collect_requirements
from travelx_agent.domain.conversation_state import ConversationStage, ConversationState
from travelx_agent.domain.message_decision import (
    ExtractedRequirement,
    MessageDecision,
    MessageIntent,
    ServiceCandidate,
)
from travelx_agent.domain.service_catalog import ServiceKey


def test_collector_normalizes_service_and_requirement_aliases() -> None:
    decision = MessageDecision(
        primary_intent=MessageIntent.SERVICE_REQUEST,
        user_goal="إنشاء موقع لمطعم",
        service_candidates=[ServiceCandidate(service_key="websites", confidence=0.95)],
        extracted_requirements=[
            ExtractedRequirement(key="project_type", value="مطعم")
        ],
        has_existing_system=False,
        needs_clarification=True,
        confidence=0.9,
    )

    result = collect_requirements(
        ConversationState(session_id="session-1"),
        decision,
        "أشتي موقع لمطعمي",
    )

    assert result.conversation.current_service is ServiceKey.WEBSITE_DEVELOPMENT
    assert result.conversation.collected_requirements["business_type"] == "مطعم"
    assert result.conversation.collected_requirements["existing_website"] == "no"
    assert result.conversation.stage is ConversationStage.REQUIREMENTS
    assert result.next_requirement is not None
    assert result.next_requirement.key == "website_goal"


def test_code_applies_semantic_summaries_proposed_by_the_model() -> None:
    message = (
        "أشتي أحمي الموقع حقي من الهجمات لأنهم اخترقوني، "
        "وأشتي العربي فقط لأن مشروعي يخص العرب"
    )
    conversation = ConversationState(
        session_id="session-2",
        stage=ConversationStage.REQUIREMENTS,
        current_service=ServiceKey.WEBSITE_DEVELOPMENT,
        collected_requirements={
            "business_type": "مطعم",
            "website_goal": "استقبال الطلبات",
            "existing_website": "yes",
        },
        last_question_key="features",
        last_question_text="ما أهم المزايا المطلوبة في الموقع؟",
    )
    model_decision = MessageDecision(
        primary_intent=MessageIntent.CLARIFICATION,
        user_goal="تحديد الحماية ولغة الواجهة",
        extracted_requirements=[
            ExtractedRequirement(
                key="features",
                value="حماية الموقع من الهجمات بعد تعرضه لاختراق سابق",
                evidence="أحمي الموقع حقي من الهجمات لأنهم اخترقوني",
            ),
            ExtractedRequirement(
                key="languages",
                value="العربية فقط",
                evidence="أشتي العربي فقط لأن مشروعي يخص العرب",
            ),
        ],
        needs_clarification=False,
        confidence=0.97,
    )

    guarded = guard_message_decision(conversation, model_decision, message)
    result = collect_requirements(conversation, guarded, message)

    assert result.conversation.collected_requirements["features"] == (
        "حماية الموقع من الهجمات بعد تعرضه لاختراق سابق"
    )
    assert result.conversation.collected_requirements["languages"] == "العربية فقط"
    assert result.conversation.stage is ConversationStage.DRAFT_REVIEW