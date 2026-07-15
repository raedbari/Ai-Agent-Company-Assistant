import asyncio

from travelx_agent.application.ports.ticket_repository import TicketRepository
from travelx_agent.domain.service_catalog import Department
from travelx_agent.domain.ticket import Ticket, TicketWriteResult


class InMemoryTicketRepository(TicketRepository):
    """In-memory adapter used for tests and local development."""

    def __init__(self) -> None:
        self._tickets_by_key: dict[str, Ticket] = {}
        self._lock = asyncio.Lock()

    async def create_once(
        self,
        idempotency_key: str,
        ticket: Ticket,
    ) -> TicketWriteResult:
        async with self._lock:
            existing = self._tickets_by_key.get(idempotency_key)
            if existing is not None:
                return TicketWriteResult(
                    ticket=existing.model_copy(deep=True),
                    created=False,
                )

            stored = ticket.model_copy(deep=True)
            self._tickets_by_key[idempotency_key] = stored

            return TicketWriteResult(
                ticket=stored.model_copy(deep=True),
                created=True,
            )

    async def list_by_department(
        self,
        department: Department,
        limit: int = 50,
    ) -> list[Ticket]:
        if limit < 1:
            return []

        async with self._lock:
            matches = [
                ticket
                for ticket in self._tickets_by_key.values()
                if ticket.assigned_department == department
            ]
            matches.sort(key=lambda ticket: ticket.created_at, reverse=True)

            return [
                ticket.model_copy(deep=True)
                for ticket in matches[:limit]
            ]

    async def count(self) -> int:
        async with self._lock:
            return len(self._tickets_by_key)