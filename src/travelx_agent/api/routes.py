from hashlib import sha256
from uuid import uuid4

from travelx_agent.domain.service_catalog import Department
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from langchain_core.exceptions import LangChainException
from langsmith import Client, tracing_context

from travelx_agent.api.dependencies import (
    provide_langsmith_client,
    provide_session_store,
    provide_traffic_guard,
    provide_workflow,
    provide_ticket_repository,
)
from travelx_agent.api.schemas import (
    ChatRequest,
    ChatResponse,
    DepartmentTicketsResponse,
)

from travelx_agent.application.message_classifier import MessageClassificationError
from travelx_agent.application.ports.session_repository import (
    SessionRepository,
    SessionRepositoryError,
    SessionWriteConflictError,
)
from travelx_agent.application.ports.ticket_repository import (
    TicketRepository,
    TicketRepositoryError,
)
from travelx_agent.application.ports.traffic_guard import (
    TrafficAction,
    TrafficGuard,
    TrafficGuardUnavailable,
)
from travelx_agent.application.ticket_feature_validator import (
    TicketFeatureValidationError,
)
from travelx_agent.core.config import Settings, get_settings

router = APIRouter(prefix="/v1", tags=["chat"])


def _client_identity(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get(settings.client_ip_header, "")
        first_address = forwarded.split(",", maxsplit=1)[0].strip()

        if first_address:
            return first_address

    return request.client.host if request.client else "unknown"

@router.get(
    "/departments/{department}/tickets",
    response_model=DepartmentTicketsResponse,
    tags=["tickets"],
)
async def list_department_tickets(
    department: Department,
    limit: int = Query(default=50, ge=1, le=100),
    tickets: TicketRepository = Depends(provide_ticket_repository),
) -> DepartmentTicketsResponse:
    try:
        department_tickets = await tickets.list_by_department(
            department,
            limit,
        )
    except TicketRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ticket storage is temporarily unavailable",
        ) from exc

    return DepartmentTicketsResponse(
        department=department,
        tickets=department_tickets,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    workflow=Depends(provide_workflow),
    sessions: SessionRepository = Depends(provide_session_store),
    traffic_guard: TrafficGuard = Depends(provide_traffic_guard),
    settings: Settings = Depends(get_settings),
    langsmith_client: Client | None = Depends(provide_langsmith_client),
) -> ChatResponse:
    session_id = request.session_id or str(uuid4())

    try:
        traffic = await traffic_guard.check(
            session_id,
            _client_identity(http_request, settings),
        )
    except TrafficGuardUnavailable as exc:
        if not settings.redis_fail_open:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Traffic protection is temporarily unavailable",
            ) from exc
    else:
        if traffic.action is not TrafficAction.ALLOW:
            detail = (
                "The session is temporarily suspended due to repeated "
                "traffic violations"
                if traffic.action is TrafficAction.TEMPORARILY_SUSPEND
                else "Too many requests; retry after the indicated delay"
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail,
                headers={
                    "Retry-After": str(traffic.retry_after_seconds),
                },
            )

    try:
        conversation = await sessions.get_or_create(session_id)
    except SessionRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversation storage is temporarily unavailable",
        ) from exc

    trace_metadata = {
        "environment": settings.app_env,
        "session_hash": sha256(session_id.encode("utf-8")).hexdigest()[:12],
        "conversation_stage": conversation.stage.value,
        "current_service": (
            conversation.current_service.value
            if conversation.current_service
            else None
        ),
        "has_ticket_draft": conversation.ticket_draft is not None,
    }

    trace_tags = [
        "travelx",
        settings.app_env,
        conversation.stage.value,
    ]

    try:
        with tracing_context(
            enabled=settings.langsmith_tracing,
            client=langsmith_client,
            project_name=settings.langsmith_project,
            tags=trace_tags,
            metadata=trace_metadata,
        ):
            result = await workflow.ainvoke(
                {
                    "message": request.message,
                    "conversation": conversation,
                    "requested_draft_version": request.draft_version,
                },
                config={
                    "run_name": "travelx_customer_workflow",
                    "tags": trace_tags,
                    "metadata": trace_metadata,
                },
            )

    except (
        MessageClassificationError,
        TicketFeatureValidationError,
        LangChainException,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider could not process the message",
        ) from exc

    except TicketRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ticket storage is temporarily unavailable",
        ) from exc

    updated_conversation = result["conversation"]
    response = result["assistant_response"]

    try:
        await sessions.save(updated_conversation)

    except SessionWriteConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The conversation changed in another request; "
                "retry this message"
            ),
        ) from exc

    except SessionRepositoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversation storage is temporarily unavailable",
        ) from exc

    return ChatResponse(
        session_id=session_id,
        reply=response.text,
        stage=response.stage,
        policy_action=response.policy_action,
        service_key=response.service_key,
        primary_department=response.primary_department,
        missing_requirements=response.missing_requirements,
        ticket_draft=updated_conversation.ticket_draft,
        ticket=updated_conversation.created_ticket,
        knowledge_sources=response.knowledge_sources,
    )