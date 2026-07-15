import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from travelx_agent.application.message_classifier import build_message_classifier
from travelx_agent.core.config import Settings
from travelx_agent.domain.conversation_state import ConversationCounters, ConversationState
from travelx_agent.domain.message_decision import MessageIntent
from travelx_agent.domain.policy_decision import PolicyAction
from travelx_agent.graph.workflow import build_customer_workflow


@pytest.mark.asyncio
async def test_workflow_classifies_allowed_message_then_applies_pricing_policy() -> None:
    response = {
        "primary_intent": "service_request",
        "secondary_intents": ["price_inquiry"],
        "user_goal": "إنشاء موقع إلكتروني لمطعم",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [
            {"service_key": "website_development", "confidence": 0.95}
        ],
        "extracted_requirements": [
            {
                "key": "business_type",
                "value": "مطعم",
                "evidence": "مطعمي",
            }
        ],
        "pricing_requested": True,
        "has_existing_system": False,
        "needs_clarification": True,
        "confidence": 0.93,
    }
    model = FakeListChatModel(responses=[json.dumps(response)])
    workflow = build_customer_workflow(
        build_message_classifier(model),
        Settings(),
    )

    result = await workflow.ainvoke(
        {
            "message": "أشتي موقع لمطعمي، كم بيكلف؟",
            "conversation": ConversationState(session_id="session-1"),
        }
    )

    assert result["classification"].primary_intent is MessageIntent.SERVICE_REQUEST
    assert result["business_policy"].action is PolicyAction.APPLY_PRICING_POLICY


@pytest.mark.asyncio
async def test_legacy_rapid_counter_does_not_block_before_model() -> None:
    response = {
        "primary_intent": "service_request",
        "secondary_intents": [],
        "user_goal": "طلب تطوير موقع",
        "language": "ar",
        "tone": "neutral",
        "service_candidates": [
            {"service_key": "website_development", "confidence": 0.94}
        ],
        "extracted_requirements": [],
        "pricing_requested": False,
        "has_existing_system": None,
        "needs_clarification": True,
        "confidence": 0.91,
    }
    model = FakeListChatModel(responses=[json.dumps(response)])
    workflow = build_customer_workflow(
        build_message_classifier(model),
        Settings(),
    )

    result = await workflow.ainvoke(
        {
            "message": "أشتي موقع",
            "conversation": ConversationState(
                session_id="session-1",
                counters=ConversationCounters(rapid_repeat_count=4),
            ),
        }
    )

    assert result["ingress_policy"].action is PolicyAction.CONTINUE
    assert result["conversation"].counters.rapid_repeat_count == 0
    assert "classification" in result
    assert "business_policy" in result
