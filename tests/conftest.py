import pytest

from travelx_agent.api.dependencies import provide_traffic_guard
from travelx_agent.core.config import Settings
from travelx_agent.infrastructure.traffic_guard import InMemoryTrafficGuard
from travelx_agent.main import app


@pytest.fixture(autouse=True)
def isolate_unit_tests_from_redis():
    """اختبارات الوحدة لا تعتمد على Redis الخارجي."""

    guard = InMemoryTrafficGuard(
        Settings(
            traffic_guard_backend="memory",
            rate_limit_session_requests=1_000,
            rate_limit_client_requests=10_000,
        )
    )

    app.dependency_overrides[provide_traffic_guard] = lambda: guard

    yield

    app.dependency_overrides.pop(provide_traffic_guard, None)