from functools import lru_cache

from fastapi import HTTPException, status
from langsmith import Client

from travelx_agent.application.department_agent import (
    DepartmentAgentConfigurationError,
    DepartmentAgentRegistry,
    build_department_agents,
)
from travelx_agent.application.knowledge_answerer import build_knowledge_answerer
from travelx_agent.application.message_classifier import build_message_classifier
from travelx_agent.application.ports.session_repository import SessionRepository
from travelx_agent.application.ports.ticket_repository import TicketRepository
from travelx_agent.application.ticket_feature_validator import (
    build_ticket_feature_validator,
)
from travelx_agent.infrastructure.database import (
    Database,
    DatabaseConfigurationError,
)
from travelx_agent.infrastructure.postgres_repositories import (
    PostgresSessionRepository,
    PostgresTicketRepository,
)
from travelx_agent.application.ports.traffic_guard import TrafficGuard
from travelx_agent.infrastructure.traffic_guard import (
    InMemoryTrafficGuard,
    RedisTrafficGuard,
)

from travelx_agent.core.config import get_settings
from travelx_agent.graph.department_subgraph import (
    build_local_department_agents,
)
from travelx_agent.graph.workflow import build_customer_workflow
from travelx_agent.infrastructure.knowledge_base import (
    KnowledgeBaseConfigurationError,
    TravelXKnowledgeBase,
)
from travelx_agent.infrastructure.model import ModelConfigurationError, build_chat_model
from travelx_agent.infrastructure.session_store import InMemorySessionStore
from travelx_agent.infrastructure.skill_registry import (
    DepartmentSkillRegistry,
    SkillRegistryConfigurationError,
)
from travelx_agent.infrastructure.ticket_repository import InMemoryTicketRepository


@lru_cache
def provide_langsmith_client() -> Client | None:
    settings = get_settings()
    if not settings.langsmith_tracing:
        return None
    if not settings.langsmith_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LangSmith tracing is enabled but LANGSMITH_API_KEY is missing",
        )
    return Client(
        api_url=settings.langsmith_endpoint,
        api_key=settings.langsmith_api_key,
        hide_inputs=settings.langsmith_hide_inputs,
        hide_outputs=settings.langsmith_hide_outputs,
    )

@lru_cache
def provide_database() -> Database:
    return Database(get_settings())

@lru_cache
def provide_ticket_repository() -> TicketRepository:
    settings = get_settings()

    if settings.persistence_backend == "postgresql":
        return PostgresTicketRepository(
            provide_database().sessions,
            settings.tenant_id,
        )

    return InMemoryTicketRepository()

@lru_cache
def provide_knowledge_base() -> TravelXKnowledgeBase:
    return TravelXKnowledgeBase.from_json_file(get_settings().knowledge_file)

@lru_cache
def provide_skill_registry() -> DepartmentSkillRegistry:
    return DepartmentSkillRegistry.from_json_file(
        get_settings().skills_file
    )

@lru_cache
def provide_traffic_guard() -> TrafficGuard:
    settings = get_settings()

    if settings.traffic_guard_backend == "redis":
        return RedisTrafficGuard(settings)

    return InMemoryTrafficGuard(settings)

@lru_cache
def _build_workflow():
    settings = get_settings()
    model = build_chat_model(settings)

    classifier = build_message_classifier(model)
    feature_validator = build_ticket_feature_validator(model)
    knowledge_answerer = build_knowledge_answerer(model)

    knowledge_base = provide_knowledge_base()
    skill_registry = provide_skill_registry()

    department_agents = build_department_agents(
        model,
        knowledge_base,
        skill_registry,
        knowledge_limit=settings.knowledge_top_k,
    )

    local_department_agents = build_local_department_agents(
      department_agents,
      settings,
)

    department_registry = DepartmentAgentRegistry(
      local_department_agents
)

    return build_customer_workflow(
        classifier,
        settings,
        feature_validator=feature_validator,
        ticket_repository=provide_ticket_repository(),
        knowledge_answerer=knowledge_answerer,
        knowledge_base=knowledge_base,
        department_agents=department_registry,    )



def provide_workflow():
    try:
        return _build_workflow()
    except (
    DatabaseConfigurationError,
    ModelConfigurationError,
    KnowledgeBaseConfigurationError,
    SkillRegistryConfigurationError,
    DepartmentAgentConfigurationError,
) as exc:
        raise


@lru_cache
def provide_session_store() -> SessionRepository:
    settings = get_settings()

    if settings.persistence_backend == "postgresql":
        return PostgresSessionRepository(
            provide_database().sessions,
            settings.tenant_id,
        )

    return InMemorySessionStore()

async def close_database() -> None:
    if get_settings().persistence_backend == "postgresql":
        await provide_database().dispose()

async def close_traffic_guard() -> None:
    await provide_traffic_guard().aclose()