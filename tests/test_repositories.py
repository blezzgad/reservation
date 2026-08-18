from typing import cast
from unittest.mock import AsyncMock, Mock

from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.models import Product, Reservation, ReservationStatus
from reservation_service.repositories import ProductRepository, ReservationRepository


async def test_product_lookup_uses_for_update() -> None:
    product = Product(id=42, sku="sku-42", available_quantity=5)
    result = Mock()
    result.scalar_one_or_none.return_value = product
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = result
    repository = ProductRepository(cast(AsyncSession, session))

    found = await repository.get_by_id_for_update(product_id=42)

    assert found is product
    execute_call = session.execute.await_args
    assert execute_call is not None
    statement = execute_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "WHERE products.id = 42" in sql
    assert sql.endswith("FOR UPDATE")


async def test_product_lookup_uses_sku() -> None:
    product = Product(id=42, sku="sku-42", available_quantity=5)
    result = Mock()
    result.scalar_one_or_none.return_value = product
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = result
    repository = ProductRepository(cast(AsyncSession, session))

    found = await repository.get_by_sku("sku-42")

    assert found is product


async def test_reservation_lookup_uses_external_id() -> None:
    reservation = Reservation(
        external_id="reservation-123",
        product_id=42,
        quantity=3,
        status=ReservationStatus.RESERVED,
    )
    result = Mock()
    result.scalar_one_or_none.return_value = reservation
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = result
    repository = ReservationRepository(cast(AsyncSession, session))

    found = await repository.get_by_external_id("reservation-123")

    assert found is reservation
    execute_call = session.execute.await_args
    assert execute_call is not None
    statement = execute_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "reservations.external_id = 'reservation-123'" in sql
    assert "FOR UPDATE" not in sql


async def test_add_flushes_without_commit() -> None:
    reservation = Reservation(
        external_id="reservation-123",
        product_id=42,
        quantity=3,
        status=ReservationStatus.RESERVED,
    )
    session = AsyncMock(spec=AsyncSession)
    repository = ReservationRepository(cast(AsyncSession, session))

    await repository.add(reservation)

    session.add.assert_called_once_with(reservation)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_awaited()


async def test_product_add_and_delete_flush_without_commit() -> None:
    product = Product(id=42, sku="sku-42", available_quantity=5)
    session = AsyncMock(spec=AsyncSession)
    repository = ProductRepository(cast(AsyncSession, session))

    await repository.add(product)
    await repository.delete(product)

    session.add.assert_called_once_with(product)
    session.delete.assert_awaited_once_with(product)
    assert session.flush.await_count == 2
    session.commit.assert_not_awaited()


async def test_reservation_exists_for_product() -> None:
    result = Mock()
    result.scalar_one.return_value = True
    session = AsyncMock(spec=AsyncSession)
    session.execute.return_value = result
    repository = ReservationRepository(cast(AsyncSession, session))

    assert await repository.exists_for_product(42) is True
