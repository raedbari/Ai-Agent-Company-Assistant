from datetime import UTC, datetime

from pydantic import BaseModel

from travelx_agent.domain.conversation_state import ConversationStage, ConversationState
from travelx_agent.domain.message_decision import MessageDecision
from travelx_agent.domain.service_catalog import (
    RequirementDefinition,
    ServiceDefinition,
    ServiceKey,
    get_service,
)


MINIMUM_EXTRACTION_CONFIDENCE = 0.70


class RequirementCollectionResult(BaseModel):
    conversation: ConversationState
    service: ServiceDefinition | None = None
    next_requirement: RequirementDefinition | None = None


REQUIREMENT_ALIASES: dict[ServiceKey, dict[str, str]] = {
    ServiceKey.WEBSITE_DEVELOPMENT: {
        "project_type": "business_type",
        "industry": "business_type",
        "purpose": "website_goal",
        "goal": "website_goal",
        "existing_system": "existing_website",
        "existing_site": "existing_website",
        "required_features": "features",
    },
    ServiceKey.HOSTING: {
        "site_type": "website_type",
        "existing_system": "existing_website",
        "traffic": "expected_traffic",
        "domain": "domain_status",
        "backup": "backup_needed",
        "security": "security_needed",
    },
    ServiceKey.AI_AGENT: {
        "purpose": "agent_goal",
        "goal": "agent_goal",
        "channel": "deployment_channel",
        "platform": "deployment_channel",
        "knowledge_sources": "data_sources",
        "actions": "agent_actions",
    },
    ServiceKey.MOBILE_APP: {
        "users": "user_types",
        "platform": "platforms",
        "required_features": "features",
    },
    ServiceKey.LOGO_DESIGN: {
        "project_name": "business_name",
        "business_type": "industry",
        "style": "preferred_style",
        "colors": "preferred_colors",
    },
}


def _choose_service(
    conversation: ConversationState,
    decision: MessageDecision,
) -> ServiceDefinition | None:
    candidates = sorted(
        decision.service_candidates,
        key=lambda candidate: candidate.confidence,
        reverse=True,
    )
    for candidate in candidates:
        service = get_service(candidate.service_key)
        if service:
            return service
    return get_service(conversation.current_service)


def _normalize_requirement_key(service: ServiceDefinition, key: str) -> str | None:
    normalized = key.strip().lower()
    allowed = {item.key for item in service.requirements}
    if normalized in allowed:
        return normalized
    alias = REQUIREMENT_ALIASES.get(service.key, {}).get(normalized)
    return alias if alias in allowed else None


def collect_requirements(
    conversation: ConversationState,
    decision: MessageDecision,
    message: str,
) -> RequirementCollectionResult:
    updated = conversation.model_copy(deep=True)
    service = _choose_service(updated, decision)
    updated.last_user_message = message
    updated.updated_at = datetime.now(UTC)

    if service is None:
        updated.stage = ConversationStage.DISCOVERY
        return RequirementCollectionResult(conversation=updated)

    updated.current_service = service.key

    if decision.confidence >= MINIMUM_EXTRACTION_CONFIDENCE:
        for extracted in decision.extracted_requirements:
            key = _normalize_requirement_key(service, extracted.key)
            summarized_value = " ".join(extracted.value.split())
            if key and summarized_value:
                updated.collected_requirements[key] = summarized_value

        if decision.has_existing_system is not None:
            existing_key = _normalize_requirement_key(service, "existing_system")
            if existing_key:
                updated.collected_requirements[existing_key] = (
                    "yes" if decision.has_existing_system else "no"
                )

    missing = [
        item
        for item in service.requirements
        if item.required and not updated.collected_requirements.get(item.key)
    ]
    updated.missing_requirements = [item.key for item in missing]
    next_requirement = missing[0] if missing else None

    if next_requirement:
        updated.stage = ConversationStage.REQUIREMENTS
        updated.last_question_key = next_requirement.key
        updated.last_question_text = next_requirement.question_ar
    else:
        updated.stage = ConversationStage.DRAFT_REVIEW
        updated.last_question_key = None
        updated.last_question_text = None

    return RequirementCollectionResult(
        conversation=updated,
        service=service,
        next_requirement=next_requirement,
    )