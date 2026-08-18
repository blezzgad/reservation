from asyncio import gather

from httpx import AsyncClient
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from reservation_service.models import Product, Reservation

pytestmark = pytest.mark.integration


async def create_product(client: AsyncClient, *, stock: int = 5) -> int:
    response = await client.post(
        "/api/v1/products",
        json={"sku": "integration-sku", "available_quantity": stock},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def get_product_stock(
    factory: async_sessionmaker[AsyncSession],
    product_id: int,
) -> int:
    async with factory() as session:
        stock = await session.scalar(
            select(Product.available_quantity).where(Product.id == product_id)
        )
    assert stock is not None
    return stock


async def get_reservation_count(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        count = await session.scalar(select(func.count()).select_from(Reservation))
    assert count is not None
    return count


async def test_uses_dedicated_test_database(
    database_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with database_session_factory() as session:
        database_name = await session.scalar(text("SELECT current_database()"))

    assert database_name == "reservation_test"


async def test_successful_reservation_decrements_stock_and_can_be_read(
    integration_client: AsyncClient,
    database_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    product_id = await create_product(integration_client, stock=5)

    create_response = await integration_client.post(
        "/api/v1/reservations",
        json={"external_id": "reservation-123", "product_id": product_id, "quantity": 3},
    )
    get_response = await integration_client.get("/api/v1/reservations/reservation-123")

    assert create_response.status_code == 201
    assert get_response.status_code == 200
    assert get_response.json() == create_response.json()
    assert await get_product_stock(database_session_factory, product_id) == 2


async def test_missing_product_and_reservation_return_404(
    integration_client: AsyncClient,
) -> None:
    create_response = await integration_client.post(
        "/api/v1/reservations",
        json={"external_id": "missing-product", "product_id": 999999, "quantity": 1},
    )
    get_response = await integration_client.get("/api/v1/reservations/missing")

    assert create_response.status_code == 404
    assert get_response.status_code == 404


async def test_insufficient_stock_rolls_back(
    integration_client: AsyncClient,
    database_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    product_id = await create_product(integration_client, stock=2)

    response = await integration_client.post(
        "/api/v1/reservations",
        json={"external_id": "too-large", "product_id": product_id, "quantity": 3},
    )

    assert response.status_code == 409
    assert await get_product_stock(database_session_factory, product_id) == 2
    assert await get_reservation_count(database_session_factory) == 0


async def test_identical_callback_is_idempotent_and_conflict_is_rejected(
    integration_client: AsyncClient,
    database_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    product_id = await create_product(integration_client, stock=5)
    payload = {"external_id": "duplicate", "product_id": product_id, "quantity": 3}

    first = await integration_client.post("/api/v1/reservations", json=payload)
    duplicate = await integration_client.post("/api/v1/reservations", json=payload)
    conflict = await integration_client.post(
        "/api/v1/reservations",
        json={**payload, "quantity": 2},
    )

    assert first.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.json() == first.json()
    assert conflict.status_code == 409
    assert await get_product_stock(database_session_factory, product_id) == 2
    assert await get_reservation_count(database_session_factory) == 1


async def test_concurrent_reservations_do_not_oversell(
    integration_client: AsyncClient,
    database_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    product_id = await create_product(integration_client, stock=5)

    responses = await gather(
        integration_client.post(
            "/api/v1/reservations",
            json={"external_id": "concurrent-a", "product_id": product_id, "quantity": 4},
        ),
        integration_client.post(
            "/api/v1/reservations",
            json={"external_id": "concurrent-b", "product_id": product_id, "quantity": 4},
        ),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
    assert await get_product_stock(database_session_factory, product_id) == 1
    assert await get_reservation_count(database_session_factory) == 1


async def test_concurrent_identical_callbacks_create_one_reservation(
    integration_client: AsyncClient,
    database_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    product_id = await create_product(integration_client, stock=5)
    payload = {"external_id": "same-callback", "product_id": product_id, "quantity": 3}

    responses = await gather(
        integration_client.post("/api/v1/reservations", json=payload),
        integration_client.post("/api/v1/reservations", json=payload),
    )

    assert sorted(response.status_code for response in responses) == [200, 201]
    assert responses[0].json() == responses[1].json()
    assert await get_product_stock(database_session_factory, product_id) == 2
    assert await get_reservation_count(database_session_factory) == 1


async def test_product_with_reservation_cannot_be_deleted(
    integration_client: AsyncClient,
) -> None:
    product_id = await create_product(integration_client)
    await integration_client.post(
        "/api/v1/reservations",
        json={"external_id": "blocks-delete", "product_id": product_id, "quantity": 1},
    )

    response = await integration_client.delete(f"/api/v1/products/{product_id}")

    assert response.status_code == 409
