from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.db.session import async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide one SQLAlchemy session per request and always close it."""

    async with async_session_factory() as session:
        yield session


SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
