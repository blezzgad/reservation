from collections.abc import AsyncIterator
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from reservation_service.api.dependencies import get_db_session
from reservation_service.core.config import get_settings
from reservation_service.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://reservation:reservation@localhost:5433/reservation_test"
)
TEST_DATABASE_URL = os.getenv("RESERVATION_TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def validate_test_database_url(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql" or url.database != "reservation_test":
        raise RuntimeError(
            "Integration tests require a PostgreSQL database named reservation_test; "
            f"refusing to use {url.render_as_string(hide_password=True)}"
        )


@pytest.fixture(scope="session")
def migrated_test_database() -> None:
    """Apply Alembic migrations only to the validated test database."""

    validate_test_database_url(TEST_DATABASE_URL)
    previous_database_url = os.environ.get("RESERVATION_DATABASE_URL")
    os.environ["RESERVATION_DATABASE_URL"] = TEST_DATABASE_URL
    get_settings.cache_clear()
    try:
        command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("RESERVATION_DATABASE_URL", None)
        else:
            os.environ["RESERVATION_DATABASE_URL"] = previous_database_url
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def database_session_factory(
    migrated_test_database: None,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Provide an isolated factory tied to the current pytest event loop."""

    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE TABLE reservations, products RESTART IDENTITY CASCADE")
        )

    try:
        yield factory
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                text("TRUNCATE TABLE reservations, products RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


@pytest_asyncio.fixture
async def integration_client(
    database_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with database_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
