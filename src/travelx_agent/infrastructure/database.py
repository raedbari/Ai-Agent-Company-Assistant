from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from travelx_agent.core.config import Settings


class DatabaseConfigurationError(RuntimeError):
    """Raised when PostgreSQL persistence cannot be configured."""


def normalize_async_database_url(url: str) -> str:
    normalized = url.strip()
    if normalized.startswith("postgresql://"):
        normalized = normalized.replace("postgresql://", "postgresql+asyncpg://", 1)
    if not normalized.startswith("postgresql+asyncpg://"):
        raise DatabaseConfigurationError(
            "DATABASE_URL must use postgresql+asyncpg://"
        )
    return normalized


class Database:
    def __init__(self, settings: Settings) -> None:
        url = normalize_async_database_url(settings.database_url)
        self.engine: AsyncEngine = create_async_engine(
            url,
            echo=settings.database_echo,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )
        self.sessions: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
        )

    async def ping(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self.engine.dispose()