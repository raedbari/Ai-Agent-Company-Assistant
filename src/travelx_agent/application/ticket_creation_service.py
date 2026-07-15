from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel

from travelx_agent.application.ports.ticket_repository import TicketRepository
from travelx_agent.domain.conversation_state import ConversationStage, ConversationState
from travelx_agent.domain.ticket import (
    Ticket,
    TicketAuditEvent,
    TicketAuditEventType,
    TicketConfirmationOutcome,
)
from travelx_agent.domain.ticket_draft import TicketDraftStatus


class TicketConfirmationResult(BaseModel):
    conversation: ConversationState
    outcome: TicketConfirmationOutcome
    ticket: Ticket | None = None
    expected_version: int | None = None


def _idempotency_key(session_id: str, draft_id: UUID, version: int) -> str:
    return f"ticket:{session_id}:{draft_id}:{version}"


def _build_ticket(conversation: ConversationState) -> Ticket:
    draft = conversation.ticket_draft
    if draft is None:
        raise ValueError("A ticket draft is required")

    now = datetime.now(UTC)
    compact_id = draft.draft_id.hex[:8].upper()
    ticket_number = f"TX-{now:%Y%m%d}-{compact_id}-V{draft.version}"
    audit_event = TicketAuditEvent(
        event_type=TicketAuditEventType.CREATED,
        session_id=conversation.session_id,
        draft_version=draft.version,
    )
    return Ticket(
        ticket_number=ticket_number,
        source_session_id=conversation.session_id,
        source_draft_id=draft.draft_id,
        source_draft_version=draft.version,
        service_key=draft.service_key,
        assigned_department=draft.primary_department,
        requirements=dict(draft.requirements),
        additional_features=list(draft.additional_features),
        customer_notes=list(draft.customer_notes),
        audit_events=[audit_event],
    )


async def confirm_and_create_ticket(
    conversation: ConversationState,
    requested_version: int | None,
    repository: TicketRepository,
) -> TicketConfirmationResult:
    updated = conversation.model_copy(deep=True)
    draft = updated.ticket_draft

    if draft is None or updated.missing_requirements:
        return TicketConfirmationResult(
            conversation=updated,
            outcome=TicketConfirmationOutcome.DRAFT_NOT_READY,
        )

    if requested_version is None:
        return TicketConfirmationResult(
            conversation=updated,
            outcome=TicketConfirmationOutcome.VERSION_REQUIRED,
            expected_version=draft.version,
        )

    if requested_version != draft.version:
        return TicketConfirmationResult(
            conversation=updated,
            outcome=TicketConfirmationOutcome.VERSION_CONFLICT,
            expected_version=draft.version,
        )

    key = _idempotency_key(updated.session_id, draft.draft_id, draft.version)
    write_result = await repository.create_once(key, _build_ticket(updated))

    draft.status = TicketDraftStatus.CONFIRMED
    draft.confirmed_version = draft.version
    updated.ticket_draft = draft
    updated.created_ticket = write_result.ticket
    updated.stage = ConversationStage.TICKET_CREATED
    updated.updated_at = datetime.now(UTC)

    outcome = (
        TicketConfirmationOutcome.CREATED
        if write_result.created
        else TicketConfirmationOutcome.ALREADY_CREATED
    )
    return TicketConfirmationResult(
        conversation=updated,
        outcome=outcome,
        ticket=write_result.ticket,
        expected_version=draft.version,
    )