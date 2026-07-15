from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator
from travelx_agent.domain.service_catalog import Department, ServiceKey


class TicketDraftStatus(StrEnum):
    REVIEW = "review"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class TicketEditOperation(StrEnum):
    ADD_FEATURE = "add_feature"
    REMOVE_FEATURE = "remove_feature"
    REPLACE_FEATURE = "replace_feature"
    ADD_NOTE = "add_note"


class FeatureDecisionAction(StrEnum):
    ACCEPT = "accept"
    REJECT_OFF_TOPIC = "reject_off_topic"
    REJECT_UNSAFE = "reject_unsafe"
    CLARIFY = "clarify"
    SUGGEST_SEPARATE_SERVICE = "suggest_separate_service"
    DUPLICATE = "duplicate"


_RESERVED_EDIT_FIELD_NAMES = frozenset(
    {
        "action",
        "edits",
        "operation",
        "target",
        "replacement",
        "requirements",
        "additional_features",
        "customer_notes",
        "feature_key",
        "feature_value",
        "normalized_feature",
        "reason_code",
        "clarification_question_ar",
        "suggested_service",
        "confidence",
    }
)

class TicketEditCommand(BaseModel):
    operation: TicketEditOperation
    target: str | None = Field(default=None, max_length=300)
    replacement: str | None = Field(default=None, max_length=300)

    @field_validator("target", "replacement")
    @classmethod
    def reject_schema_field_names(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = " ".join(value.split()).casefold()

        if normalized in _RESERVED_EDIT_FIELD_NAMES:
            raise ValueError(
                "Ticket edits must contain actual feature text, "
                "not a schema field name"
            )

        return value
    
class TicketDraft(BaseModel):
    draft_id: UUID = Field(default_factory=uuid4)
    version: int = Field(default=1, ge=1)
    status: TicketDraftStatus = TicketDraftStatus.REVIEW
    service_key: ServiceKey
    primary_department: Department
    requirements: dict[str, str] = Field(default_factory=dict)
    additional_features: list[str] = Field(default_factory=list)
    customer_notes: list[str] = Field(default_factory=list)
    confirmed_version: int | None = Field(default=None, ge=1)


class TicketFeatureDecision(BaseModel):
    action: FeatureDecisionAction
    edits: list[TicketEditCommand] = Field(default_factory=list, max_length=8)
    reason_code: str = Field(min_length=1, max_length=100)
    clarification_question_ar: str | None = Field(default=None, max_length=300)
    suggested_service: ServiceKey | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class AppliedTicketEdit(BaseModel):
    operation: TicketEditOperation
    item: str


class TicketEditResult(BaseModel):
    draft: TicketDraft
    applied: bool
    response_key: str
    changes: list[AppliedTicketEdit] = Field(default_factory=list)