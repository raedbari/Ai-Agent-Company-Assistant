from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from travelx_agent.domain.service_catalog import ServiceKey, normalize_service_key


class MessageIntent(StrEnum):
    GREETING = "greeting"
    SERVICE_QUESTION = "service_question"
    SERVICE_REQUEST = "service_request"
    PRICE_INQUIRY = "price_inquiry"
    TICKET_EDIT = "ticket_edit"
    TICKET_CONFIRM = "ticket_confirm"
    TICKET_CANCEL = "ticket_cancel"
    TICKET_STATUS = "ticket_status"
    HUMAN_REQUEST = "human_request"
    CLARIFICATION = "clarification"
    OFF_TOPIC = "off_topic"
    ABUSE = "abuse"
    UNKNOWN = "unknown"


class MessageTone(StrEnum):
    NEUTRAL = "neutral"
    CONFUSED = "confused"
    FRUSTRATED = "frustrated"
    ABUSIVE = "abusive"


class ServiceCandidate(BaseModel):
    service_key: ServiceKey
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("service_key", mode="before")
    @classmethod
    def normalize_legacy_service_keys(cls, value: object) -> ServiceKey:
        if not isinstance(value, (str, ServiceKey)):
            raise ValueError("service_key must be a string")
        return normalize_service_key(value)


class ExtractedRequirement(BaseModel):
    key: str
    value: str
    evidence: str | None = None


class MessageDecision(BaseModel):
    primary_intent: MessageIntent
    secondary_intents: list[MessageIntent] = Field(default_factory=list)
    user_goal: str
    language: str = "ar"
    tone: MessageTone = MessageTone.NEUTRAL
    service_candidates: list[ServiceCandidate] = Field(default_factory=list)
    extracted_requirements: list[ExtractedRequirement] = Field(default_factory=list)
    pricing_requested: bool = False
    pricing_evidence: str | None = None
    has_existing_system: bool | None = None
    has_existing_system_evidence: str | None = None
    needs_clarification: bool = False
    confidence: float = Field(ge=0.0, le=1.0)