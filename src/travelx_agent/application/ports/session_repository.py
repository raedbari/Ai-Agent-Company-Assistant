from typing import Protocol

from travelx_agent.domain.conversation_state import ConversationState


class SessionRepositoryError(RuntimeError):
    """Base error for durable conversation-session storage."""


class SessionWriteConflictError(SessionRepositoryError):
    """Raised when another request has already updated the same session."""


class SessionRepository(Protocol):
    async def get_or_create(self, session_id: str) -> ConversationState:
        """Load a detached state or create a new session at revision zero."""

    async def save(self, state: ConversationState) -> None:
        """Persist only if the stored revision still matches the supplied state."""