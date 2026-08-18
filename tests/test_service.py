from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.exceptions import (
    InsufficientStockError,
    ProductNotFoundError,
    ReservationConflictError,
    ReservationNotFoundError,
)
from reservation_service.models import Product, Reservation, ReservationStatus
from reservation_service.schemas import ReservationCreate
from reservation_service.services import ReservationService


def create_service() -> tuple[ReservationService, AsyncMock]:
    session = AsyncMock(spec=AsyncSession)
    return ReservationService(cast(AsyncSession, session)), session


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


def make_payload(*, product_id: int = 42, quantity: int = 3) -> ReservationCreate:
    return ReservationCreate(
        external_id="reservation-123",
        product_id=product_id,
        quantity=quantity,
    )


def make_reservation(*, product_id: int = 42, quantity: int = 3) -> Reservation:
    return Reservation(
        external_id="reservation-123",
        product_id=product_id,
        quantity=quantity,
        status=ReservationStatus.RESERVED,
    )


async def test_successful_reservation_decrements_stock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, session = create_service()
    product = Product(id=42, sku="sku-42", available_quantity=5)
    lookup = mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
        side_effect=[None, None],
    )
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
        return_value=product,
    )
    add = mock_async_method(monkeypatch, service._reservations, "add")

    reservation = await service.create_reservation(make_payload())

    assert product.available_quantity == 2
    assert reservation.external_id == "reservation-123"
    assert reservation.status is ReservationStatus.RESERVED
    assert lookup.await_count == 2
    add.assert_awaited_once_with(reservation)
    session.begin.assert_called_once_with()


async def test_identical_existing_reservation_is_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = create_service()
    existing = make_reservation()
    mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
        return_value=existing,
    )
    product_lookup = mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
    )

    reservation = await service.create_reservation(make_payload())

    assert reservation is existing
    product_lookup.assert_not_awaited()


async def test_conflicting_existing_reservation_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = create_service()
    mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
        return_value=make_reservation(quantity=2),
    )

    with pytest.raises(ReservationConflictError):
        await service.create_reservation(make_payload(quantity=3))


async def test_product_not_found_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = create_service()
    mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
    )
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
    )

    with pytest.raises(ProductNotFoundError):
        await service.create_reservation(make_payload())


async def test_insufficient_stock_does_not_decrement_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = create_service()
    product = Product(id=42, sku="sku-42", available_quantity=2)
    mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
        side_effect=[None, None],
    )
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
        return_value=product,
    )
    add = mock_async_method(monkeypatch, service._reservations, "add")

    with pytest.raises(InsufficientStockError):
        await service.create_reservation(make_payload(quantity=3))

    assert product.available_quantity == 2
    add.assert_not_awaited()


async def test_duplicate_committed_while_waiting_for_product_lock_is_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = create_service()
    product = Product(id=42, sku="sku-42", available_quantity=2)
    existing = make_reservation(quantity=3)
    mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
        side_effect=[None, existing],
    )
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
        return_value=product,
    )
    add = mock_async_method(monkeypatch, service._reservations, "add")

    reservation = await service.create_reservation(make_payload(quantity=3))

    assert reservation is existing
    assert product.available_quantity == 2
    add.assert_not_awaited()


async def test_unique_race_returns_identical_winner(monkeypatch: pytest.MonkeyPatch) -> None:
    service, session = create_service()
    product = Product(id=42, sku="sku-42", available_quantity=5)
    existing = make_reservation()
    mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
        side_effect=[None, None, existing],
    )
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
        return_value=product,
    )
    integrity_error = IntegrityError("INSERT", {}, Exception("duplicate"))
    mock_async_method(
        monkeypatch,
        service._reservations,
        "add",
        side_effect=integrity_error,
    )

    reservation = await service.create_reservation(make_payload())

    assert reservation is existing
    assert session.begin.call_count == 2
    exit_calls = session.begin.return_value.__aexit__.await_args_list
    assert exit_calls[0].args[0] is IntegrityError
    assert exit_calls[1].args[0] is None


async def test_unique_race_rejects_conflicting_winner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = create_service()
    product = Product(id=42, sku="sku-42", available_quantity=5)
    mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
        side_effect=[None, None, make_reservation(quantity=2)],
    )
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
        return_value=product,
    )
    mock_async_method(
        monkeypatch,
        service._reservations,
        "add",
        side_effect=IntegrityError("INSERT", {}, Exception("duplicate")),
    )

    with pytest.raises(ReservationConflictError):
        await service.create_reservation(make_payload(quantity=3))


async def test_unrelated_integrity_error_is_not_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _ = create_service()
    product = Product(id=42, sku="sku-42", available_quantity=5)
    integrity_error = IntegrityError("INSERT", {}, Exception("other constraint"))
    mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
        side_effect=[None, None, None],
    )
    mock_async_method(
        monkeypatch,
        service._products,
        "get_by_id_for_update",
        return_value=product,
    )
    mock_async_method(
        monkeypatch,
        service._reservations,
        "add",
        side_effect=integrity_error,
    )

    with pytest.raises(IntegrityError) as error_info:
        await service.create_reservation(make_payload())

    assert error_info.value is integrity_error


async def test_get_existing_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = create_service()
    existing = make_reservation()
    mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
        return_value=existing,
    )

    reservation = await service.get_reservation("reservation-123")

    assert reservation is existing


async def test_get_missing_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _ = create_service()
    mock_async_method(
        monkeypatch,
        service._reservations,
        "get_by_external_id",
    )

    with pytest.raises(ReservationNotFoundError):
        await service.get_reservation("missing")
