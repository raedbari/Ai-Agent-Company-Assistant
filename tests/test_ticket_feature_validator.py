import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from travelx_agent.application.ticket_draft_service import build_ticket_draft
from travelx_agent.application.ticket_feature_validator import (
    build_ticket_feature_validator,
    validate_ticket_feature,
)
from travelx_agent.domain.conversation_state import ConversationState
from travelx_agent.domain.service_catalog import ServiceKey
from travelx_agent.domain.ticket_draft import FeatureDecisionAction


@pytest.mark.asyncio
async def test_validator_returns_structured_off_topic_decision() -> None:
    model_response = {
        "action": "reject_off_topic",
        "edits": [],
        "reason_code": "not_a_website_feature",
        "clarification_question_ar": None,
        "suggested_service": None,
        "confidence": 0.97,
    }
    model = FakeListChatModel(responses=[json.dumps(model_response)])
    validator = build_ticket_feature_validator(model)
    conversation = ConversationState(
        session_id="session-1",
        current_service=ServiceKey.WEBSITE_DEVELOPMENT,
        collected_requirements={"business_type": "مطعم"},
        missing_requirements=[],
    )
    draft = build_ticket_draft(conversation)

    result = await validate_ticket_feature(validator, draft, "أضف كتاب")

    assert result.action is FeatureDecisionAction.REJECT_OFF_TOPIC
    assert result.edits == []