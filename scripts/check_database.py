import asyncio

from sqlalchemy import inspect

from travelx_agent.core.config import get_settings
from travelx_agent.infrastructure.database import Database


EXPECTED_TABLES = {
    "alembic_version",
    "conversation_sessions",
    "ticket_audit_events",
    "tickets",
}


async def main() -> None:
    settings = get_settings()
    database = Database(settings)
    try:
        await database.ping()
        async with database.engine.connect() as connection:
            tables = await connection.run_sync(
                lambda sync_connection: set(
                    inspect(sync_connection).get_table_names()
                )
            )
    finally:
        await database.dispose()

    missing = EXPECTED_TABLES - tables
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise SystemExit(f"Database connected, but migrations are missing: {missing_text}")
    print("PostgreSQL connection and Travel-X schema are ready.")


if __name__ == "__main__":
    asyncio.run(main())