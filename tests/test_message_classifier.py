import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from travelx_agent.application.message_classifier import (
    build_message_classifier,
    classify_message,
)
from travelx_agent.domain.message_decision import MessageIntent


@pytest.mark.asyncio
async def test_classifier_returns_structured_multi_intent_decision() -> None:
    response = {
        "primary_intent": "service_request",
        "secondary_intents": ["price_inquiry"],
        "user_goal": "إضافة وكيل ذكاء اصطناعي إلى موقع موجود",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [
            {"service_key": "ai_agent", "confidence": 0.95},
            {"service_key": "website_integration", "confidence": 0.78},
        ],
        "extracted_requirements": [
            {"key": "existing_website", "value": "true"}
        ],
        "pricing_requested": True,
        "has_existing_system": True,
        "needs_clarification": True,
        "confidence": 0.92,
    }
    model = FakeListChatModel(responses=[json.dumps(response)])
    classifier = build_message_classifier(model)

    result = await classify_message(
        classifier,
        "أشتي وكيل ذكاء اصطناعي داخل موقعي وكم سعره؟",
    )

    assert result.primary_intent is MessageIntent.SERVICE_REQUEST
    assert MessageIntent.PRICE_INQUIRY in result.secondary_intents
    assert result.pricing_requested is True
