from travelx_agent.application.ticket_draft_service import (
    apply_ticket_edit,
    build_ticket_draft,
)
from travelx_agent.domain.conversation_state import ConversationState
from travelx_agent.domain.service_catalog import ServiceKey
from travelx_agent.domain.ticket_draft import (
    FeatureDecisionAction,
    TicketEditCommand,
    TicketEditOperation,
    TicketFeatureDecision,
)


def make_complete_website_conversation() -> ConversationState:
    return ConversationState(
        session_id="session-1",
        current_service=ServiceKey.WEBSITE_DEVELOPMENT,
        collected_requirements={
            "business_type": "مطعم",
            "website_goal": "عرض المطعم واستقبال الطلبات",
            "existing_website": "no",
            "features": "قائمة الطعام",
            "languages": "العربية",
        },
        missing_requirements=[],
    )


def test_safe_relevant_feature_is_added_as_new_draft_version() -> None:
    draft = build_ticket_draft(make_complete_website_conversation())
    decision = TicketFeatureDecision(
        action=FeatureDecisionAction.ACCEPT,
        edits=[
            TicketEditCommand(
                operation=TicketEditOperation.ADD_FEATURE,
                target="الدفع الإلكتروني",
            )
        ],
        reason_code="relevant_website_feature",
        confidence=0.96,
    )

    result = apply_ticket_edit(draft, decision)

    assert result.applied is True
    assert result.draft.version == 2
    assert result.draft.additional_features == ["الدفع الإلكتروني"]
    assert draft.additional_features == []


def test_unsafe_feature_decision_never_mutates_draft() -> None:
    draft = build_ticket_draft(make_complete_website_conversation())
    decision = TicketFeatureDecision(
        action=FeatureDecisionAction.REJECT_UNSAFE,
        edits=[],
        reason_code="unsafe_capability",
        confidence=0.99,
    )

    result = apply_ticket_edit(draft, decision)

    assert result.applied is False
    assert result.draft.version == 1
    assert result.draft.additional_features == []


def test_low_confidence_acceptance_is_converted_to_clarification() -> None:
    draft = build_ticket_draft(make_complete_website_conversation())
    decision = TicketFeatureDecision(
        action=FeatureDecisionAction.ACCEPT,
        edits=[
            TicketEditCommand(
                operation=TicketEditOperation.ADD_FEATURE,
                target="ميزة غير واضحة",
            )
        ],
        reason_code="uncertain_relevance",
        confidence=0.52,
    )

    result = apply_ticket_edit(draft, decision)

    assert result.applied is False
    assert result.response_key == "low_confidence_clarification"
    assert result.draft.version == 1


def test_multiple_features_are_applied_in_one_new_draft_version() -> None:
    draft = build_ticket_draft(make_complete_website_conversation())
    decision = TicketFeatureDecision(
        action=FeatureDecisionAction.ACCEPT,
        edits=[
            TicketEditCommand(
                operation=TicketEditOperation.ADD_FEATURE,
                target="حماية التطبيق من الهجمات",
            ),
            TicketEditCommand(
                operation=TicketEditOperation.ADD_FEATURE,
                target="تحسين استهلاك الرموز وتقليل التكلفة التشغيلية",
            ),
        ],
        reason_code="multiple_relevant_features",
        confidence=0.97,
    )

    result = apply_ticket_edit(draft, decision)

    assert result.applied is True
    assert result.draft.version == 2
    assert result.draft.additional_features == [
        "حماية التطبيق من الهجمات",
        "تحسين استهلاك الرموز وتقليل التكلفة التشغيلية",
    ]
    assert len(result.changes) == 2