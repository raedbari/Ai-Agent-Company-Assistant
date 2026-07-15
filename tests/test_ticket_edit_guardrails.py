import pytest
from pydantic import ValidationError

from travelx_agent.application.ticket_draft_service import apply_ticket_edit
from travelx_agent.domain.ticket_draft import (
    TicketDraft,
    TicketFeatureDecision,
)


def test_ticket_edit_rejects_schema_field_as_feature() -> None:
    with pytest.raises(ValidationError):
        TicketFeatureDecision.model_validate(
            {
                "action": "accept",
                "edits": [
                    {
                        "operation": "add_feature",
                        "target": "additional_features",
                    }
                ],
                "reason_code": "feature_added",
                "confidence": 0.95,
            }
        )


def test_ticket_edit_stores_actual_feature_text() -> None:
    draft = TicketDraft(
        service_key="website_development",
        primary_department="txsaas",
    )
    decision = TicketFeatureDecision.model_validate(
        {
            "action": "accept",
            "edits": [
                {
                    "operation": "add_feature",
                    "target": "عرض الصور كصور متحركة",
                }
            ],
            "reason_code": "feature_added",
            "confidence": 0.95,
        }
    )

    result = apply_ticket_edit(draft, decision)

    assert result.applied is True
    assert result.draft.version == 2
    assert result.draft.additional_features == [
        "عرض الصور كصور متحركة"
    ]