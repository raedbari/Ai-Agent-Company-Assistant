import asyncio

import pytest

from travelx_agent.application.ticket_creation_service import (
    confirm_and_create_ticket,
)
from travelx_agent.domain.conversation_state import (
    ConversationStage,
    ConversationState,
)
from travelx_agent.domain.service_catalog import Department, ServiceKey
from travelx_agent.domain.ticket import (
    TicketAuditEventType,
    TicketConfirmationOutcome,
)
from travelx_agent.domain.ticket_draft import TicketDraft, TicketDraftStatus
from travelx_agent.infrastructure.ticket_repository import InMemoryTicketRepository


def make_review_conversation(session_id: str = "ticket-session") -> ConversationState:
    requirements = {
        "business_type": "مطعم",
        "website_goal": "عرض قائمة الطعام واستقبال الطلبات",
        "existing_website": "no",
        "features": "قائمة الطعام والطلبات",
        "languages": "العربية",
    }
    return ConversationState(
        session_id=session_id,
        stage=ConversationStage.DRAFT_REVIEW,
        current_service=ServiceKey.WEBSITE_DEVELOPMENT,
        collected_requirements=requirements,
        missing_requirements=[],
        ticket_draft=TicketDraft(
            service_key=ServiceKey.WEBSITE_DEVELOPMENT,
            primary_department=Department.TXSAAS,
            requirements=requirements,
        ),
    )


@pytest.mark.asyncio
async def test_confirmation_requires_an_explicit_draft_version() -> None:
    repository = InMemoryTicketRepository()

    result = await confirm_and_create_ticket(
        make_review_conversation(),
        requested_version=None,
        repository=repository,
    )

    assert result.outcome is TicketConfirmationOutcome.VERSION_REQUIRED
    assert result.expected_version == 1
    assert result.conversation.stage is ConversationStage.DRAFT_REVIEW
    assert result.conversation.created_ticket is None
    assert await repository.count() == 0


@pytest.mark.asyncio
async def test_stale_draft_version_never_creates_a_ticket() -> None:
    repository = InMemoryTicketRepository()

    result = await confirm_and_create_ticket(
        make_review_conversation(),
        requested_version=2,
        repository=repository,
    )

    assert result.outcome is TicketConfirmationOutcome.VERSION_CONFLICT
    assert result.expected_version == 1
    assert result.conversation.created_ticket is None
    assert await repository.count() == 0


@pytest.mark.asyncio
async def test_matching_version_creates_and_audits_the_ticket() -> None:
    repository = InMemoryTicketRepository()

    result = await confirm_and_create_ticket(
        make_review_conversation(),
        requested_version=1,
        repository=repository,
    )

    assert result.outcome is TicketConfirmationOutcome.CREATED
    assert result.ticket is not None
    assert result.ticket.assigned_department is Department.TXSAAS
    assert result.ticket.source_draft_version == 1
    assert result.ticket.audit_events[0].event_type is TicketAuditEventType.CREATED
    assert result.conversation.stage is ConversationStage.TICKET_CREATED
    assert result.conversation.ticket_draft is not None
    assert result.conversation.ticket_draft.status is TicketDraftStatus.CONFIRMED
    assert result.conversation.ticket_draft.confirmed_version == 1
    assert await repository.count() == 1


@pytest.mark.asyncio
async def test_repeating_the_same_confirmation_returns_the_existing_ticket() -> None:
    repository = InMemoryTicketRepository()
    first = await confirm_and_create_ticket(
        make_review_conversation(),
        requested_version=1,
        repository=repository,
    )

    second = await confirm_and_create_ticket(
        first.conversation,
        requested_version=1,
        repository=repository,
    )

    assert first.ticket is not None
    assert second.ticket is not None
    assert second.outcome is TicketConfirmationOutcome.ALREADY_CREATED
    assert second.ticket.ticket_id == first.ticket.ticket_id
    assert second.ticket.ticket_number == first.ticket.ticket_number
    assert await repository.count() == 1


@pytest.mark.asyncio
async def test_concurrent_confirmations_still_create_only_one_ticket() -> None:
    repository = InMemoryTicketRepository()
    conversation = make_review_conversation()

    first, second = await asyncio.gather(
        confirm_and_create_ticket(conversation, 1, repository),
        confirm_and_create_ticket(conversation, 1, repository),
    )

    assert {first.outcome, second.outcome} == {
        TicketConfirmationOutcome.CREATED,
        TicketConfirmationOutcome.ALREADY_CREATED,
    }
    assert first.ticket is not None
    assert second.ticket is not None
    assert first.ticket.ticket_id == second.ticket.ticket_id
    assert await repository.count() == 1