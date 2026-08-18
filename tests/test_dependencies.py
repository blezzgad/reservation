from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.api.dependencies import get_db_session


async def test_session_dependency_yields_async_session() -> None:
    dependency = get_db_session()

    session = await anext(dependency)

    assert isinstance(session, AsyncSession)
    await dependency.aclose()
