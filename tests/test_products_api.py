from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import cast
from unittest.mock import Mock

from httpx import ASGITransport, AsyncClient
import pytest

from reservation_service.api.dependencies import get_product_service
from reservation_service.exceptions import (
    ProductInUseError,
    ProductNotFoundError,
    ProductSkuConflictError,
)
from reservation_service.main import app
from reservation_service.models import Product
from reservation_service.services import ProductService


def make_product() -> Product:
    timestamp = datetime.now(UTC)
    return Product(
        id=42,
        sku="sku-42",
        available_quantity=5,
        created_at=timestamp,
        updated_at=timestamp,
    )


@pytest.fixture
def product_service_mock() -> Iterator[Mock]:
    service = Mock(spec=ProductService)

    def override_service() -> ProductService:
        return cast(ProductService, service)

    app.dependency_overrides[get_product_service] = override_service
    yield service
    app.dependency_overrides.clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def test_create_product_returns_201(
    client: AsyncClient,
    product_service_mock: Mock,
) -> None:
    product_service_mock.create_product.return_value = make_product()

    response = await client.post(
        "/api/v1/products",
        json={"sku": "sku-42", "available_quantity": 5},
    )

    assert response.status_code == 201
    assert response.json()["id"] == 42
    assert response.json()["sku"] == "sku-42"
    assert response.json()["available_quantity"] == 5


async def test_create_duplicate_sku_returns_409(
    client: AsyncClient,
    product_service_mock: Mock,
) -> None:
    error = ProductSkuConflictError("sku-42")
    product_service_mock.create_product.side_effect = error

    response = await client.post(
        "/api/v1/products",
        json={"sku": "sku-42", "available_quantity": 5},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": str(error)}


async def test_create_product_rejects_negative_quantity(
    client: AsyncClient,
    product_service_mock: Mock,
) -> None:
    response = await client.post(
        "/api/v1/products",
        json={"sku": "sku-42", "available_quantity": -1},
    )

    assert response.status_code == 422
    product_service_mock.create_product.assert_not_awaited()


async def test_delete_product_returns_204(
    client: AsyncClient,
    product_service_mock: Mock,
) -> None:
    response = await client.delete("/api/v1/products/42")

    assert response.status_code == 204
    assert response.content == b""
    product_service_mock.delete_product.assert_awaited_once_with(42)


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(ProductNotFoundError(42), 404), (ProductInUseError(42), 409)],
)
async def test_delete_maps_application_errors(
    client: AsyncClient,
    product_service_mock: Mock,
    error: Exception,
    expected_status: int,
) -> None:
    product_service_mock.delete_product.side_effect = error

    response = await client.delete("/api/v1/products/42")

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


async def test_delete_rejects_non_positive_id(
    client: AsyncClient,
    product_service_mock: Mock,
) -> None:
    response = await client.delete("/api/v1/products/0")

    assert response.status_code == 422
    product_service_mock.delete_product.assert_not_awaited()
