import json

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable

from travelx_agent.domain.service_catalog import catalog_prompt_context, get_service
from travelx_agent.domain.ticket_draft import TicketDraft, TicketFeatureDecision
from travelx_agent.prompts.ticket_feature_validator import (
    TICKET_FEATURE_VALIDATOR_PROMPT,
)


class TicketFeatureValidationError(RuntimeError):
    """Raised when the model cannot return a valid ticket edit decision."""


def build_ticket_feature_validator(model: BaseChatModel) -> Runnable:
    parser = PydanticOutputParser(pydantic_object=TicketFeatureDecision)
    prompt = TICKET_FEATURE_VALIDATOR_PROMPT.partial(
        format_instructions=parser.get_format_instructions(),
        catalog_context=catalog_prompt_context(),
    )
    json_model = model.bind(response_format={"type": "json_object"})
    return prompt | json_model | parser


async def validate_ticket_feature(
    validator: Runnable,
    draft: TicketDraft,
    message: str,
) -> TicketFeatureDecision:
    service = get_service(draft.service_key)
    service_context = {
        "service_key": draft.service_key.value,
        "name_ar": service.name_ar if service else None,
        "description_ar": service.description_ar if service else None,
        "primary_department": draft.primary_department.value,
    }
    validation_feedback = (
    "The previous response violated the schema. "
    "Use actual feature or note text in target and replacement. "
    "Never use JSON field names such as additional_features, "
    "customer_notes, requirements, target, or replacement. "
    "An accept decision must contain one or more valid edit objects. "
    "Return corrected JSON only."
)

    for attempt in range(2):
        try:
            result = await validator.ainvoke(
                {
                    "service_context": json.dumps(service_context, ensure_ascii=False),
                    "draft_context": draft.model_dump_json(),
                    "message": message,
                    "validation_feedback": validation_feedback,
                }
            )
            return TicketFeatureDecision.model_validate(result)
        except (OutputParserException, ValueError) as exc:
            if attempt == 1:
                raise TicketFeatureValidationError(
                    "The model returned an invalid ticket edit decision twice"
                ) from exc
            validation_feedback = (
                "The previous response violated the schema. An accept decision must "
                "contain one or more edit objects. A clarify decision must contain "
                "a specific Arabic clarification question. Return corrected JSON only."
            )

    raise TicketFeatureValidationError("Ticket feature validation failed")