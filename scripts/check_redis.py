import asyncio

from travelx_agent.core.config import get_settings
from travelx_agent.infrastructure.traffic_guard import RedisTrafficGuard


async def main() -> None:
    settings = get_settings()
    guard = RedisTrafficGuard(settings)
    try:
        await guard.ping()
        decision = await guard.check("redis-health-session", "redis-health-client")
    finally:
        await guard.aclose()

    print("Redis connection: OK")
    print(f"Traffic decision: {decision.action.value}")
    print(f"Session count: {decision.session_count}")


if __name__ == "__main__":
    asyncio.run(main())