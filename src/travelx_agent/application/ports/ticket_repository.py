from typing import Protocol

from travelx_agent.domain.service_catalog import Department
from travelx_agent.domain.ticket import Ticket, TicketWriteResult


class TicketRepositoryError(RuntimeError):
    """Raised when ticket persistence is unavailable or fails."""


class TicketRepository(Protocol):
    async def create_once(
        self,
        idempotency_key: str,
        ticket: Ticket,
    ) -> TicketWriteResult:
        """Persist a ticket atomically, returning the existing one on a retry."""

    async def list_by_department(
        self,
        department: Department,
        limit: int = 50,
    ) -> list[Ticket]:
        """Return the newest tickets assigned to one department."""