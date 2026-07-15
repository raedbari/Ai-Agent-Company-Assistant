from travelx_agent.domain.conversation_state import ConversationState
from travelx_agent.domain.service_catalog import get_service
from travelx_agent.domain.ticket_draft import (
    AppliedTicketEdit,
    FeatureDecisionAction,
    TicketDraft,
    TicketEditOperation,
    TicketEditResult,
    TicketFeatureDecision,
)


MINIMUM_ACCEPT_CONFIDENCE = 0.75


def build_ticket_draft(conversation: ConversationState) -> TicketDraft:
    service = get_service(conversation.current_service)
    if service is None:
        raise ValueError("A canonical service is required before building a ticket draft")
    if conversation.missing_requirements:
        raise ValueError("Required fields must be complete before building a ticket draft")

    if conversation.ticket_draft is not None:
        return conversation.ticket_draft.model_copy(deep=True)

    return TicketDraft(
        service_key=service.key,
        primary_department=service.primary_department,
        requirements=dict(conversation.collected_requirements),
    )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _find_index(items: list[str], target: str) -> int | None:
    normalized_target = target.casefold()
    for index, item in enumerate(items):
        if item.casefold() == normalized_target:
            return index
    return None


def apply_ticket_edit(
    draft: TicketDraft,
    decision: TicketFeatureDecision,
) -> TicketEditResult:
    if decision.action is not FeatureDecisionAction.ACCEPT:
        return TicketEditResult(
            draft=draft.model_copy(deep=True),
            applied=False,
            response_key=decision.action.value,
        )

    if decision.confidence < MINIMUM_ACCEPT_CONFIDENCE:
        return TicketEditResult(
            draft=draft.model_copy(deep=True),
            applied=False,
            response_key="low_confidence_clarification",
        )

    if not decision.edits:
        return TicketEditResult(
            draft=draft.model_copy(deep=True),
            applied=False,
            response_key="invalid_edit_command",
        )

    updated = draft.model_copy(deep=True)
    changes: list[AppliedTicketEdit] = []

    for command in decision.edits:
        target = _clean(command.target)
        replacement = _clean(command.replacement)

        if command.operation is TicketEditOperation.ADD_FEATURE:
            if target is None:
                return TicketEditResult(
                    draft=draft.model_copy(deep=True),
                    applied=False,
                    response_key="invalid_edit_command",
                )
            if _find_index(updated.additional_features, target) is not None:
                continue
            updated.additional_features.append(target)
            changes.append(
                AppliedTicketEdit(operation=command.operation, item=target)
            )

        elif command.operation is TicketEditOperation.REMOVE_FEATURE:
            if target is None:
                return TicketEditResult(
                    draft=draft.model_copy(deep=True),
                    applied=False,
                    response_key="invalid_edit_command",
                )
            index = _find_index(updated.additional_features, target)
            if index is None:
                return TicketEditResult(
                    draft=draft.model_copy(deep=True),
                    applied=False,
                    response_key="feature_not_found",
                )
            removed = updated.additional_features.pop(index)
            changes.append(
                AppliedTicketEdit(operation=command.operation, item=removed)
            )

        elif command.operation is TicketEditOperation.REPLACE_FEATURE:
            if target is None or replacement is None:
                return TicketEditResult(
                    draft=draft.model_copy(deep=True),
                    applied=False,
                    response_key="invalid_edit_command",
                )
            index = _find_index(updated.additional_features, target)
            if index is None:
                return TicketEditResult(
                    draft=draft.model_copy(deep=True),
                    applied=False,
                    response_key="feature_not_found",
                )
            updated.additional_features[index] = replacement
            changes.append(
                AppliedTicketEdit(operation=command.operation, item=replacement)
            )

        elif command.operation is TicketEditOperation.ADD_NOTE:
            if target is None:
                return TicketEditResult(
                    draft=draft.model_copy(deep=True),
                    applied=False,
                    response_key="invalid_edit_command",
                )
            if _find_index(updated.customer_notes, target) is not None:
                continue
            updated.customer_notes.append(target)
            changes.append(
                AppliedTicketEdit(operation=command.operation, item=target)
            )

    if not changes:
        return TicketEditResult(
            draft=draft.model_copy(deep=True),
            applied=False,
            response_key=FeatureDecisionAction.DUPLICATE.value,
        )

    updated.version += 1
    updated.confirmed_version = None
    return TicketEditResult(
        draft=updated,
        applied=True,
        response_key="batch_edit_applied",
        changes=changes,
    )