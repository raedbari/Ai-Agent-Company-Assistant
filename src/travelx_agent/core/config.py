from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Travel-X Customer Agent"
    app_env: str = "development"

    openrouter_api_key: str = ""
    openrouter_model: str = "deepseek/deepseek-v4-flash"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_url: str = "https://travel-x.online"
    openrouter_app_title: str = "Travel-X Customer Agent"

    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "travelx-customer-agent-dev"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_dataset: str = "travelx-semantic-regression-v1"
    langsmith_hide_inputs: bool = True
    langsmith_hide_outputs: bool = True

    knowledge_file: str = "knowledge/travelx_knowledge.json"
    knowledge_top_k: int = 4

    skills_file: str = "skills/travelx_department_skills.json"
    department_agent_attempt_timeout_seconds: float = Field(
     default=8.0,
     gt=0,
     le=60,
)

    department_agent_total_timeout_seconds: float = Field(
     default=20.0,
     gt=0,
     le=120,
)

    department_agent_max_attempts: int = Field(
     default=2,
     ge=1,
     le=3,
)

    persistence_backend: Literal["memory", "postgresql"] = "memory"
    tenant_id: str = "travelx"
    database_url: str = (
     "postgresql+asyncpg://postgres:change_me@localhost:5432/travelx_agent"
)
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    persistence_backend: Literal["memory", "postgresql"] = "memory"
    tenant_id: str = "travelx"
    database_url: str = (
        "postgresql+asyncpg://postgres:change_me@localhost:5432/travelx_agent"
    )
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    exact_repeat_human_check_threshold: int = 3
    exact_repeat_suspend_threshold: int = 5
    semantic_repeat_human_check_threshold: int = 3
    semantic_repeat_suspend_threshold: int = 5
    rapid_repeat_human_check_threshold: int = 4
    rapid_repeat_suspend_threshold: int = 7
    clarification_handoff_threshold: int = 3
    temporary_suspension_seconds: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    traffic_guard_backend: Literal["memory", "redis"] = "memory"

    redis_url: str = "redis://localhost:6379/0"
    redis_key_prefix: str = "travelx"
    redis_socket_timeout_seconds: float = 2.0
    redis_fail_open: bool = False

    rate_limit_window_seconds: int = 60
    rate_limit_session_requests: int = 20
    rate_limit_client_requests: int = 200
    rate_limit_violation_limit: int = 3
    rate_limit_suspend_seconds: int = 600

    trust_proxy_headers: bool = False
    client_ip_header: str = "CF-Connecting-IP"

    


@lru_cache
def get_settings() -> Settings:
    return Settings()