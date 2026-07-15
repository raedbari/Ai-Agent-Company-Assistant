from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from travelx_agent.domain.service_catalog import Department
from travelx_agent.application.ports.session_repository import (
    SessionRepository,
    SessionRepositoryError,
    SessionWriteConflictError,
)
from travelx_agent.application.ports.ticket_repository import (
    TicketRepository,
    TicketRepositoryError,
)
from travelx_agent.domain.conversation_state import ConversationState
from travelx_agent.domain.ticket import Ticket, TicketAuditEvent, TicketWriteResult
from travelx_agent.infrastructure.database_models import (
    ConversationSessionRecord,
    TicketAuditEventRecord,
    TicketRecord,
)


def _conversation_payload(state: ConversationState) -> dict:
    return state.model_dump(mode="json", exclude={"revision"})


class PostgresSessionRepository(SessionRepository):
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        tenant_id: str,
    ) -> None:
        self._sessions = sessions
        self._tenant_id = tenant_id

    async def get_or_create(self, session_id: str) -> ConversationState:
        new_state = ConversationState(session_id=session_id)
        insert_statement = (
            postgres_insert(ConversationSessionRecord)
            .values(
                tenant_id=self._tenant_id,
                session_id=session_id,
                stage=new_state.stage.value,
                current_service=None,
                state=_conversation_payload(new_state),
                revision=0,
                created_at=new_state.created_at,
                updated_at=new_state.updated_at,
            )
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "session_id"],
            )
        )
        select_statement = select(ConversationSessionRecord).where(
            ConversationSessionRecord.tenant_id == self._tenant_id,
            ConversationSessionRecord.session_id == session_id,
        )

        try:
            async with self._sessions() as database_session:
                async with database_session.begin():
                    await database_session.execute(insert_statement)
                    record = (
                        await database_session.execute(select_statement)
                    ).scalar_one()
        except SQLAlchemyError as exc:
            raise SessionRepositoryError("Could not load the conversation session") from exc

        payload = dict(record.state)
        payload["revision"] = record.revision
        return ConversationState.model_validate(payload)

    async def save(self, state: ConversationState) -> None:
        next_revision = state.revision + 1
        statement = (
            update(ConversationSessionRecord)
            .where(
                ConversationSessionRecord.tenant_id == self._tenant_id,
                ConversationSessionRecord.session_id == state.session_id,
                ConversationSessionRecord.revision == state.revision,
            )
            .values(
                stage=state.stage.value,
                current_service=(
                    state.current_service.value if state.current_service else None
                ),
                state=_conversation_payload(state),
                revision=next_revision,
                updated_at=state.updated_at,
            )
        )

        try:
            async with self._sessions() as database_session:
                async with database_session.begin():
                    result = await database_session.execute(statement)
                    if result.rowcount != 1:
                        raise SessionWriteConflictError(
                            f"Session {state.session_id!r} has a newer revision"
                        )
        except SessionWriteConflictError:
            raise
        except SQLAlchemyError as exc:
            raise SessionRepositoryError("Could not save the conversation session") from exc


def _ticket_values(tenant_id: str, idempotency_key: str, ticket: Ticket) -> dict:
    return {
        "ticket_id": ticket.ticket_id,
        "tenant_id": tenant_id,
        "idempotency_key": idempotency_key,
        "ticket_number": ticket.ticket_number,
        "status": ticket.status.value,
        "source_session_id": ticket.source_session_id,
        "source_draft_id": ticket.source_draft_id,
        "source_draft_version": ticket.source_draft_version,
        "service_key": ticket.service_key.value,
        "assigned_department": ticket.assigned_department.value,
        "requirements": dict(ticket.requirements),
        "additional_features": list(ticket.additional_features),
        "customer_notes": list(ticket.customer_notes),
        "created_at": ticket.created_at,
    }


def _ticket_from_records(
    ticket_record: TicketRecord,
    audit_records: Sequence[TicketAuditEventRecord],
) -> Ticket:
    return Ticket(
        ticket_id=ticket_record.ticket_id,
        ticket_number=ticket_record.ticket_number,
        status=ticket_record.status,
        source_session_id=ticket_record.source_session_id,
        source_draft_id=ticket_record.source_draft_id,
        source_draft_version=ticket_record.source_draft_version,
        service_key=ticket_record.service_key,
        assigned_department=ticket_record.assigned_department,
        requirements=dict(ticket_record.requirements),
        additional_features=list(ticket_record.additional_features),
        customer_notes=list(ticket_record.customer_notes),
        audit_events=[
            TicketAuditEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                actor_type=event.actor_type,
                session_id=event.session_id,
                draft_version=event.draft_version,
                occurred_at=event.occurred_at,
            )
            for event in audit_records
        ],
        created_at=ticket_record.created_at,
    )

class PostgresTicketRepository(TicketRepository):
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        tenant_id: str,
    ) -> None:
        self._sessions = sessions
        self._tenant_id = tenant_id

    async def create_once(
        self,
        idempotency_key: str,
        ticket: Ticket,
    ) -> TicketWriteResult:
        insert_statement = (
            postgres_insert(TicketRecord)
            .values(**_ticket_values(self._tenant_id, idempotency_key, ticket))
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "idempotency_key"],
            )
            .returning(TicketRecord.ticket_id)
        )

        try:
            async with self._sessions() as database_session:
                async with database_session.begin():
                    inserted_id = (
                        await database_session.execute(insert_statement)
                    ).scalar_one_or_none()

                    if inserted_id is not None:
                        database_session.add_all(
                            [
                                TicketAuditEventRecord(
                                    event_id=event.event_id,
                                    ticket_id=ticket.ticket_id,
                                    event_type=event.event_type.value,
                                    actor_type=event.actor_type,
                                    session_id=event.session_id,
                                    draft_version=event.draft_version,
                                    occurred_at=event.occurred_at,
                                )
                                for event in ticket.audit_events
                            ]
                        )
                        stored_ticket = ticket.model_copy(deep=True)
                        created = True
                    else:
                        ticket_record = (
                            await database_session.execute(
                                select(TicketRecord).where(
                                    TicketRecord.tenant_id == self._tenant_id,
                                    TicketRecord.idempotency_key == idempotency_key,
                                )
                            )
                        ).scalar_one()

                        audit_records = (
                            await database_session.execute(
                                select(TicketAuditEventRecord)
                                .where(
                                    TicketAuditEventRecord.ticket_id
                                    == ticket_record.ticket_id
                                )
                                .order_by(TicketAuditEventRecord.occurred_at)
                            )
                        ).scalars().all()

                        stored_ticket = _ticket_from_records(
                            ticket_record,
                            audit_records,
                        )
                        created = False

        except SQLAlchemyError as exc:
            raise TicketRepositoryError(
                "Could not create the ticket"
            ) from exc

        return TicketWriteResult(
            ticket=stored_ticket,
            created=created,
        )

    async def list_by_department(
        self,
        department: Department,
        limit: int = 50,
    ) -> list[Ticket]:
        if limit < 1:
            return []

        ticket_statement = (
            select(TicketRecord)
            .where(
                TicketRecord.tenant_id == self._tenant_id,
                TicketRecord.assigned_department == department.value,
            )
            .order_by(
                TicketRecord.created_at.desc(),
                TicketRecord.ticket_id.desc(),
            )
            .limit(limit)
        )

        try:
            async with self._sessions() as database_session:
                ticket_records = (
                    await database_session.execute(ticket_statement)
                ).scalars().all()

                if not ticket_records:
                    return []

                ticket_ids = [
                    record.ticket_id
                    for record in ticket_records
                ]

                audit_records = (
                    await database_session.execute(
                        select(TicketAuditEventRecord)
                        .where(
                            TicketAuditEventRecord.ticket_id.in_(ticket_ids)
                        )
                        .order_by(
                            TicketAuditEventRecord.ticket_id,
                            TicketAuditEventRecord.occurred_at,
                        )
                    )
                ).scalars().all()

        except SQLAlchemyError as exc:
            raise TicketRepositoryError(
                "Could not list department tickets"
            ) from exc

        audits_by_ticket_id = {
            ticket_id: []
            for ticket_id in ticket_ids
        }

        for audit_record in audit_records:
            audits_by_ticket_id[audit_record.ticket_id].append(
                audit_record
            )

        return [
            _ticket_from_records(
                ticket_record,
                audits_by_ticket_id[ticket_record.ticket_id],
            )
            for ticket_record in ticket_records
        ]

    async def count(self) -> int:
        try:
            async with self._sessions() as database_session:
                value = await database_session.scalar(
                    select(func.count(TicketRecord.ticket_id)).where(
                        TicketRecord.tenant_id == self._tenant_id
                    )
                )

        except SQLAlchemyError as exc:
            raise TicketRepositoryError(
                "Could not count tickets"
            ) from exc

        return int(value or 0)