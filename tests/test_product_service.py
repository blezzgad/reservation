from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.exceptions import (
    ProductInUseError,
    ProductNotFoundError,
    ProductSkuConflictError,
)
from reservation_service.models import Product
from reservation_service.schemas import ProductCreate
from reservation_service.services import ProductService


def create_service() -> tuple[ProductService, AsyncMock]:
    session = AsyncMock(spec=AsyncSession)
    return ProductService(cast(AsyncSession, session)), session


def mock_async_method(
    monkeypatch: pytest.MonkeyPatch,
    target: object,
    name: str,
    *,
    return_value: object | None = None,
    side_effect: object | None = None,
) -> AsyncMock:
    method = AsyncMock(return_value=return_value, side_effect=side_effect)
    monkeypatch.setattr(target, name, method)
    return method


def make_payload() -> ProductCreate:
    return ProductCreate(sku="sku-42", available_quantity=5)


async def test_create_product(monkeypatch: pytest.MonkeyPatch) -> None:
    service, session = create_service()
    mock_async_method(monkeypatch, service._products, "get_by_sku")
    add = mock_async_method(monkeypatch, service._products, "add")

    product = await service.create_product(make_payload())

    assert product.sku == "sku-42"
    assert product.available_quantity == 5
    add.assert_awaited_once_with(product)
    session.begin.assert_called_once_with()


async def test_duplicate_sku_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = create_service()
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_sku",
        return_value=Product(id=42, sku="sku-42", available_quantity=5),
    )

    with pytest.raises(ProductSkuConflictError):
        await service.create_product(make_payload())


async def test_concurrent_duplicate_sku_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    service, session = create_service()
    existing = Product(id=42, sku="sku-42", available_quantity=5)
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_sku",
        side_effect=[None, existing],
    )
    mock_async_method(
        monkeypatch,
        service._products,
        "add",
        side_effect=IntegrityError("INSERT", {}, Exception("duplicate")),
    )

    with pytest.raises(ProductSkuConflictError):
        await service.create_product(make_payload())

    assert session.begin.call_count == 2


async def test_delete_product(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = create_service()
    product = Product(id=42, sku="sku-42", available_quantity=5)
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
        return_value=product,
    )
    mock_async_method(
        monkeypatch,
        service._reservations,
        "exists_for_product",
        return_value=False,
    )
    delete = mock_async_method(monkeypatch, service._products, "delete")

    await service.delete_product(42)

    delete.assert_awaited_once_with(product)


async def test_delete_missing_product_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = create_service()
    mock_async_method(monkeypatch, service._products, "get_by_id_for_update")

    with pytest.raises(ProductNotFoundError):
        await service.delete_product(42)


async def test_delete_product_with_reservations_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = create_service()
    product = Product(id=42, sku="sku-42", available_quantity=5)
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
        return_value=product,
    )
    mock_async_method(
        monkeypatch,
        service._reservations,
        "exists_for_product",
        return_value=True,
    )
    delete = mock_async_method(monkeypatch, service._products, "delete")

    with pytest.raises(ProductInUseError):
        await service.delete_product(42)

    delete.assert_not_awaited()


async def test_delete_fk_race_is_mapped_to_product_in_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, session = create_service()
    product = Product(id=42, sku="sku-42", available_quantity=5)
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
        return_value=product,
    )
    mock_async_method(
        monkeypatch,
        service._reservations,
        "exists_for_product",
        side_effect=[False, True],
    )
    mock_async_method(
        monkeypatch,
        service._products,
        "delete",
        side_effect=IntegrityError("DELETE", {}, Exception("foreign key")),
    )

    with pytest.raises(ProductInUseError):
        await service.delete_product(42)

    assert session.begin.call_count == 2
