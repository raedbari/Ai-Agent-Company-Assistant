import httpx
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from travelx_agent.core.config import Settings


class ModelConfigurationError(RuntimeError):
    """Raised when the model cannot be configured safely."""


def build_chat_model(settings: Settings) -> ChatOpenAI:
    if not settings.openrouter_api_key:
        raise ModelConfigurationError(
            "OPENROUTER_API_KEY is not configured"
        )

    timeout = httpx.Timeout(
        timeout=30.0,
        connect=10.0,
    )

    sync_client = httpx.Client(
        transport=httpx.HTTPTransport(
            local_address="0.0.0.0",
            retries=0,
        ),
        timeout=timeout,
        trust_env=False,
    )

    async_client = httpx.AsyncClient(
        transport=httpx.AsyncHTTPTransport(
            local_address="0.0.0.0",
            retries=0,
        ),
        timeout=timeout,
        trust_env=False,
    )

    return ChatOpenAI(
        model=settings.openrouter_model,
        api_key=SecretStr(settings.openrouter_api_key),
        base_url=settings.openrouter_base_url,
        temperature=0,
        max_retries=0,
        timeout=timeout,
        http_client=sync_client,
        http_async_client=async_client,
        default_headers={
            "HTTP-Referer": settings.openrouter_app_url,
            "X-OpenRouter-Title": settings.openrouter_app_title,
        },
    )