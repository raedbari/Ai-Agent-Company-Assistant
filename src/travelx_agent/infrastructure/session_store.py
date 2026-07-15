import asyncio

from travelx_agent.domain.conversation_state import ConversationState

from travelx_agent.application.ports.session_repository import (
    SessionRepository,
    SessionWriteConflictError,
)

class InMemorySessionStore(SessionRepository):
    """Temporary session storage; replaced by PostgreSQL in the production phase."""

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationState] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, session_id: str) -> ConversationState:
        async with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                state = ConversationState(session_id=session_id)
                self._sessions[session_id] = state
            return state.model_copy(deep=True)

    async def save(self, state: ConversationState) -> None:
       async with self._lock:
        existing = self._sessions.get(state.session_id)

        if existing is None:
            self._sessions[state.session_id] = state.model_copy(deep=True)
            return

        if existing.revision != state.revision:
            raise SessionWriteConflictError(
                f"Session {state.session_id!r} was updated by another request"
            )

        stored = state.model_copy(deep=True)
        stored.revision += 1
        self._sessions[state.session_id] = stored
