from typing import cast
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.api.dependencies import (
    get_db_session,
    get_product_service,
    get_reservation_service,
)
from reservation_service.services import ProductService, ReservationService


async def test_session_dependency_yields_async_session() -> None:
    dependency = get_db_session()

    session = await anext(dependency)

    assert isinstance(session, AsyncSession)
    await dependency.aclose()


def test_reservation_service_dependency_uses_request_session() -> None:
    session = AsyncMock(spec=AsyncSession)

    service = get_reservation_service(cast(AsyncSession, session))

    assert isinstance(service, ReservationService)
    assert service._session is session


def test_product_service_dependency_uses_request_session() -> None:
    session = AsyncMock(spec=AsyncSession)

    service = get_product_service(cast(AsyncSession, session))

    assert isinstance(service, ProductService)
    assert service._session is session
