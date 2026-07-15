import pytest

from travelx_agent.application.ports.session_repository import (
    SessionWriteConflictError,
)
from travelx_agent.domain.conversation_state import ConversationStage
from travelx_agent.infrastructure.database import (
    DatabaseConfigurationError,
    normalize_async_database_url,
)
from travelx_agent.infrastructure.database_models import Base
from travelx_agent.infrastructure.session_store import InMemorySessionStore


def test_database_url_is_normalized_for_asyncpg() -> None:
    result = normalize_async_database_url(
        "postgresql://postgres:secret@localhost/travelx_agent"
    )

    assert result.startswith("postgresql+asyncpg://")


def test_non_postgresql_database_url_is_rejected() -> None:
    with pytest.raises(DatabaseConfigurationError):
        normalize_async_database_url("sqlite:///travelx.db")


def test_persistence_metadata_contains_required_tables() -> None:
    assert {
        "conversation_sessions",
        "tickets",
        "ticket_audit_events",
    }.issubset(Base.metadata.tables)


@pytest.mark.asyncio
async def test_in_memory_repository_rejects_a_stale_session_write() -> None:
    repository = InMemorySessionStore()
    first = await repository.get_or_create("concurrent-session")
    stale = await repository.get_or_create("concurrent-session")

    first.stage = ConversationStage.DISCOVERY
    await repository.save(first)

    stale.stage = ConversationStage.REQUIREMENTS
    with pytest.raises(SessionWriteConflictError):
        await repository.save(stale)

    stored = await repository.get_or_create("concurrent-session")
    assert stored.stage is ConversationStage.DISCOVERY
    assert stored.revision == 1