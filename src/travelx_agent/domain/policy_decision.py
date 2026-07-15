from enum import StrEnum

from pydantic import BaseModel


class PolicyAction(StrEnum):
    CONTINUE = "continue"
    EXPLAIN_DIFFERENTLY = "explain_differently"
    APPLY_PRICING_POLICY = "apply_pricing_policy"
    OFFER_HUMAN_HANDOFF = "offer_human_handoff"
    REQUIRE_HUMAN_CHECK = "require_human_check"
    TEMPORARILY_SUSPEND = "temporarily_suspend"


class PolicyDecision(BaseModel):
    action: PolicyAction
    allow_model_call: bool
    allow_freeform_response: bool
    allow_ticket_creation: bool
    reason_code: str
    response_key: str | None = None

