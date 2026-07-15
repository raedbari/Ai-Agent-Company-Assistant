from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field


class TrafficAction(StrEnum):
    ALLOW = "allow"
    RATE_LIMIT = "rate_limit"
    TEMPORARILY_SUSPEND = "temporarily_suspend"


class TrafficDecision(BaseModel):
    action: TrafficAction
    retry_after_seconds: int = Field(default=0, ge=0)
    session_count: int = Field(default=0, ge=0)
    client_count: int = Field(default=0, ge=0)
    reason_code: str


class TrafficGuardUnavailable(RuntimeError):
    """Raised when the distributed traffic guard cannot make a safe decision."""


class TrafficGuard(Protocol):
    async def check(self, session_id: str, client_id: str) -> TrafficDecision: ...

    async def aclose(self) -> None: ...