from fastapi.testclient import TestClient
import pytest

from travelx_agent.api.dependencies import provide_traffic_guard, provide_workflow
from travelx_agent.application.ports.traffic_guard import (
    TrafficAction,
    TrafficDecision,
)
from travelx_agent.core.config import Settings
from travelx_agent.infrastructure.traffic_guard import (
    InMemoryTrafficGuard,
    RedisTrafficGuard,
)
from travelx_agent.main import app


class MutableClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class StaticTrafficGuard:
    def __init__(self, decision: TrafficDecision) -> None:
        self.decision = decision

    async def check(self, session_id: str, client_id: str) -> TrafficDecision:
        return self.decision

    async def aclose(self) -> None:
        return None


class NeverCalledWorkflow:
    async def ainvoke(self, *_args, **_kwargs):
        raise AssertionError("The workflow must not run after traffic is blocked")


class FakeRedis:
    def __init__(self, result: list[int]) -> None:
        self.result = result
        self.last_call: tuple | None = None

    async def eval(self, *args):
        self.last_call = args
        return self.result

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_in_memory_guard_limits_then_suspends_repeated_violations() -> None:
    clock = MutableClock()
    settings = Settings(
        rate_limit_window_seconds=60,
        rate_limit_session_requests=2,
        rate_limit_client_requests=20,
        rate_limit_violation_limit=2,
        rate_limit_suspend_seconds=30,
    )
    guard = InMemoryTrafficGuard(settings, clock=clock)

    assert (await guard.check("session-1", "client-1")).action is TrafficAction.ALLOW
    assert (await guard.check("session-1", "client-1")).action is TrafficAction.ALLOW
    assert (await guard.check("session-1", "client-1")).action is TrafficAction.RATE_LIMIT

    suspended = await guard.check("session-1", "client-1")
    assert suspended.action is TrafficAction.TEMPORARILY_SUSPEND
    assert suspended.retry_after_seconds == 30

    still_suspended = await guard.check("session-1", "client-1")
    assert still_suspended.action is TrafficAction.TEMPORARILY_SUSPEND


@pytest.mark.asyncio
async def test_redis_guard_maps_atomic_script_result_and_hashes_identifiers() -> None:
    fake_redis = FakeRedis([1, 17, 3, 4])
    guard = RedisTrafficGuard(Settings(), client=fake_redis)  # type: ignore[arg-type]

    decision = await guard.check("private-session-id", "203.0.113.7")

    assert decision.action is TrafficAction.RATE_LIMIT
    assert decision.retry_after_seconds == 17
    assert fake_redis.last_call is not None
    rendered_call = " ".join(map(str, fake_redis.last_call))
    assert "private-session-id" not in rendered_call
    assert "203.0.113.7" not in rendered_call


def test_api_returns_429_without_running_langgraph() -> None:
    guard = StaticTrafficGuard(
        TrafficDecision(
            action=TrafficAction.RATE_LIMIT,
            retry_after_seconds=42,
            reason_code="request_rate_exceeded",
        )
    )
    app.dependency_overrides[provide_traffic_guard] = lambda: guard
    app.dependency_overrides[provide_workflow] = lambda: NeverCalledWorkflow()

    try:
        response = TestClient(app).post(
            "/v1/chat",
            json={"message": "مرحبا", "session_id": "blocked-session"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.headers["retry-after"] == "42"
