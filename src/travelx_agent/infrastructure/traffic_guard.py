import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic

from redis.asyncio import Redis
from redis.exceptions import RedisError

from travelx_agent.application.ports.traffic_guard import (
    TrafficAction,
    TrafficDecision,
    TrafficGuardUnavailable,
)
from travelx_agent.core.config import Settings


_REDIS_TRAFFIC_SCRIPT = """
local suspended_ttl = redis.call('TTL', KEYS[4])
if suspended_ttl > 0 then
    return {2, suspended_ttl, 0, 0}
end

local session_count = redis.call('INCR', KEYS[1])
if session_count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end

local client_count = redis.call('INCR', KEYS[2])
if client_count == 1 then
    redis.call('EXPIRE', KEYS[2], ARGV[1])
end

if session_count > tonumber(ARGV[2]) or client_count > tonumber(ARGV[3]) then
    local violations = redis.call('INCR', KEYS[3])
    if violations == 1 then
        redis.call('EXPIRE', KEYS[3], ARGV[5])
    end

    if violations >= tonumber(ARGV[4]) then
        redis.call('SET', KEYS[4], '1', 'EX', ARGV[5])
        return {2, tonumber(ARGV[5]), session_count, client_count}
    end

    local session_ttl = redis.call('TTL', KEYS[1])
    local client_ttl = redis.call('TTL', KEYS[2])
    local retry_after = math.max(session_ttl, client_ttl, 1)
    return {1, retry_after, session_count, client_count}
end

return {0, 0, session_count, client_count}
"""


@dataclass
class _Counter:
    count: int
    expires_at: float


class InMemoryTrafficGuard:
    """Single-process implementation for development and deterministic tests."""

    def __init__(
        self,
        settings: Settings,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._session_counters: dict[str, _Counter] = {}
        self._client_counters: dict[str, _Counter] = {}
        self._violations: dict[str, _Counter] = {}
        self._suspended_until: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def check(self, session_id: str, client_id: str) -> TrafficDecision:
        async with self._lock:
            now = self._clock()
            subject = self._subject_key(session_id, client_id)
            suspended_until = self._suspended_until.get(subject, 0.0)
            if suspended_until > now:
                return TrafficDecision(
                    action=TrafficAction.TEMPORARILY_SUSPEND,
                    retry_after_seconds=max(1, int(suspended_until - now)),
                    reason_code="temporary_suspension_active",
                )
            self._suspended_until.pop(subject, None)

            session_count, session_expires = self._increment(
                self._session_counters,
                self._hash(session_id),
                now,
                self._settings.rate_limit_window_seconds,
            )
            client_count, client_expires = self._increment(
                self._client_counters,
                self._hash(client_id),
                now,
                self._settings.rate_limit_window_seconds,
            )

            over_limit = (
                session_count > self._settings.rate_limit_session_requests
                or client_count > self._settings.rate_limit_client_requests
            )
            if not over_limit:
                return TrafficDecision(
                    action=TrafficAction.ALLOW,
                    session_count=session_count,
                    client_count=client_count,
                    reason_code="traffic_allowed",
                )

            violations, _ = self._increment(
                self._violations,
                subject,
                now,
                self._settings.rate_limit_suspend_seconds,
            )
            if violations >= self._settings.rate_limit_violation_limit:
                self._suspended_until[subject] = (
                    now + self._settings.rate_limit_suspend_seconds
                )
                return TrafficDecision(
                    action=TrafficAction.TEMPORARILY_SUSPEND,
                    retry_after_seconds=self._settings.rate_limit_suspend_seconds,
                    session_count=session_count,
                    client_count=client_count,
                    reason_code="repeated_rate_limit_violations",
                )

            return TrafficDecision(
                action=TrafficAction.RATE_LIMIT,
                retry_after_seconds=max(
                    1,
                    int(max(session_expires, client_expires) - now),
                ),
                session_count=session_count,
                client_count=client_count,
                reason_code="request_rate_exceeded",
            )

    async def aclose(self) -> None:
        return None

    @staticmethod
    def _increment(
        counters: dict[str, _Counter],
        key: str,
        now: float,
        ttl_seconds: int,
    ) -> tuple[int, float]:
        counter = counters.get(key)
        if counter is None or counter.expires_at <= now:
            counter = _Counter(count=0, expires_at=now + ttl_seconds)
        counter.count += 1
        counters[key] = counter
        return counter.count, counter.expires_at

    @classmethod
    def _subject_key(cls, session_id: str, client_id: str) -> str:
        return f"{cls._hash(session_id)}:{cls._hash(client_id)}"

    @staticmethod
    def _hash(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()[:24]


class RedisTrafficGuard:
    """Atomic distributed traffic guard shared by all API replicas."""

    def __init__(
        self,
        settings: Settings,
        *,
        client: Redis | None = None,
    ) -> None:
        self._settings = settings
        self._redis = client or Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_timeout_seconds,
            socket_timeout=settings.redis_socket_timeout_seconds,
        )

    async def check(self, session_id: str, client_id: str) -> TrafficDecision:
        keys = self._keys(session_id, client_id)
        arguments = (
            self._settings.rate_limit_window_seconds,
            self._settings.rate_limit_session_requests,
            self._settings.rate_limit_client_requests,
            self._settings.rate_limit_violation_limit,
            self._settings.rate_limit_suspend_seconds,
        )
        try:
            raw = await self._redis.eval(
                _REDIS_TRAFFIC_SCRIPT,
                len(keys),
                *keys,
                *arguments,
            )
        except RedisError as exc:
            raise TrafficGuardUnavailable("Redis traffic guard is unavailable") from exc

        action_code, retry_after, session_count, client_count = map(int, raw)
        action = {
            0: TrafficAction.ALLOW,
            1: TrafficAction.RATE_LIMIT,
            2: TrafficAction.TEMPORARILY_SUSPEND,
        }[action_code]
        reason_code = {
            TrafficAction.ALLOW: "traffic_allowed",
            TrafficAction.RATE_LIMIT: "request_rate_exceeded",
            TrafficAction.TEMPORARILY_SUSPEND: "temporary_suspension_active",
        }[action]
        return TrafficDecision(
            action=action,
            retry_after_seconds=retry_after,
            session_count=session_count,
            client_count=client_count,
            reason_code=reason_code,
        )

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except RedisError as exc:
            raise TrafficGuardUnavailable("Redis traffic guard is unavailable") from exc

    async def aclose(self) -> None:
        await self._redis.aclose()

    def _keys(self, session_id: str, client_id: str) -> tuple[str, str, str, str]:
        tenant_hash = self._hash(self._settings.tenant_id)[:12]
        session_hash = self._hash(session_id)
        client_hash = self._hash(client_id)
        subject_hash = self._hash(f"{session_id}:{client_id}")
        base = f"{self._settings.redis_key_prefix}:{{{tenant_hash}}}:traffic"
        return (
            f"{base}:session:{session_hash}",
            f"{base}:client:{client_hash}",
            f"{base}:violations:{subject_hash}",
            f"{base}:suspended:{subject_hash}",
        )

    @staticmethod
    def _hash(value: str) -> str:
        return sha256(value.encode("utf-8")).hexdigest()[:24]