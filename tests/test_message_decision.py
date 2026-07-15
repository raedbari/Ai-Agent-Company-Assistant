import pytest
from pydantic import ValidationError

from travelx_agent.domain.message_decision import (
    MessageDecision,
    MessageIntent,
    ServiceCandidate,
)


def test_message_can_contain_service_request_and_price_question() -> None:
    decision = MessageDecision(
        primary_intent=MessageIntent.SERVICE_REQUEST,
        secondary_intents=[MessageIntent.PRICE_INQUIRY],
        user_goal="إنشاء موقع إلكتروني لمطعم ومعرفة التكلفة",
        service_candidates=[
            ServiceCandidate(service_key="website_development", confidence=0.93)
        ],
        pricing_requested=True,
        needs_clarification=True,
        confidence=0.91,
    )

    assert decision.pricing_requested is True
    assert decision.primary_intent is MessageIntent.SERVICE_REQUEST


def test_confidence_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValidationError):
        MessageDecision(
            primary_intent=MessageIntent.UNKNOWN,
            user_goal="غير واضح",
            confidence=1.5,
        )
