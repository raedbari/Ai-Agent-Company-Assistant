from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable

from travelx_agent.domain.message_decision import MessageDecision
from travelx_agent.domain.service_catalog import catalog_prompt_context
from travelx_agent.prompts.message_classifier import MESSAGE_CLASSIFIER_PROMPT


class MessageClassificationError(RuntimeError):
    """Raised when a message cannot be classified into the required contract."""


def build_message_classifier(model: BaseChatModel) -> Runnable:
    parser = PydanticOutputParser(pydantic_object=MessageDecision)
    prompt = MESSAGE_CLASSIFIER_PROMPT.partial(
        format_instructions=parser.get_format_instructions(),
        catalog_context=catalog_prompt_context(),
    )
    json_model = model.bind(response_format={"type": "json_object"})
    return prompt | json_model | parser


def _has_verbatim_evidence(
    evidence: str | None,
    message: str,
) -> bool:
    if not evidence:
        return False

    candidate = evidence.strip()
    return bool(candidate) and candidate in message


def _invalid_requirement_evidence(
    decision: MessageDecision,
    message: str,
) -> list[str]:
    return [
        requirement.key
        for requirement in decision.extracted_requirements
        if not _has_verbatim_evidence(requirement.evidence, message)
    ]


def _merge_grounded_requirements(
    original: MessageDecision,
    correction: MessageDecision,
    message: str,
) -> MessageDecision:
    """Keep valid facts from both attempts and discard ungrounded claims."""
    corrected_by_key = {
        requirement.key.strip().lower(): requirement
        for requirement in correction.extracted_requirements
        if _has_verbatim_evidence(requirement.evidence, message)
    }

    merged = []
    seen_keys: set[str] = set()

    for requirement in original.extracted_requirements:
        key = requirement.key.strip().lower()
        selected = (
            requirement
            if _has_verbatim_evidence(requirement.evidence, message)
            else corrected_by_key.get(key)
        )

        if selected is None or key in seen_keys:
            continue

        merged.append(selected)
        seen_keys.add(key)

    for key, requirement in corrected_by_key.items():
        if key not in seen_keys:
            merged.append(requirement)
            seen_keys.add(key)

    return original.model_copy(
        deep=True,
        update={"extracted_requirements": merged},
    )


async def classify_message(
    classifier: Runnable,
    message: str,
    conversation_context: str = "No previous conversation context.",
) -> MessageDecision:
    """Classify once, retry once on invalid JSON/evidence, and merge valid facts."""
    validation_feedback = (
        "No previous attempt. Copy every evidence value as one contiguous "
        "verbatim substring from the current customer message."
    )
    original_decision: MessageDecision | None = None

    for attempt in range(2):
        try:
            result = await classifier.ainvoke(
                {
                    "message": message,
                    "conversation_context": conversation_context,
                    "validation_feedback": validation_feedback,
                }
            )
            decision = MessageDecision.model_validate(result)
        except (OutputParserException, ValueError) as exc:
            if attempt == 1:
                if original_decision is not None:
                    return _merge_grounded_requirements(
                        original_decision,
                        original_decision,
                        message,
                    )
                raise MessageClassificationError(
                    "The model returned an invalid classification twice"
                ) from exc

            validation_feedback = (
                "The previous response violated the JSON schema. "
                "Return one complete corrected JSON object."
            )
            continue

        invalid_keys = _invalid_requirement_evidence(decision, message)

        if not invalid_keys:
            if original_decision is None:
                return decision
            return _merge_grounded_requirements(
                original_decision,
                decision,
                message,
            )

        if attempt == 0:
            original_decision = decision
            validation_feedback = (
                "The previous response contained requirement evidence that was "
                "not one contiguous verbatim substring from the customer message. "
                "Re-extract every explicit requirement and correct all evidence. "
                "Do not combine separated phrases or rewrite any evidence. "
                f"Invalid keys: {', '.join(invalid_keys)}."
            )
            continue

        if original_decision is not None:
            return _merge_grounded_requirements(
                original_decision,
                decision,
                message,
            )

        return _merge_grounded_requirements(decision, decision, message)

    raise MessageClassificationError("Message classification failed")
