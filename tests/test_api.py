from collections.abc import AsyncIterator, Iterator
from typing import cast
from unittest.mock import AsyncMock, Mock

from httpx import ASGITransport, AsyncClient
import pytest

from reservation_service import main as main_module
from reservation_service.api.dependencies import get_reservation_service
from reservation_service.exceptions import (
    InsufficientStockError,
    ProductNotFoundError,
    ReservationConflictError,
    ReservationNotFoundError,
)
from reservation_service.main import app
from reservation_service.models import Reservation, ReservationStatus
from reservation_service.services import ReservationResult, ReservationService


def make_reservation() -> Reservation:
    return Reservation(
        external_id="reservation-123",
        product_id=42,
        quantity=3,
        status=ReservationStatus.RESERVED,
    )


@pytest.fixture
def service_mock() -> Iterator[Mock]:
    service = Mock(spec=ReservationService)

    def override_service() -> ReservationService:
        return cast(ReservationService, service)

    app.dependency_overrides[get_reservation_service] = override_service
    yield service
    app.dependency_overrides.clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_lifespan_disposes_database_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    dispose_engine = AsyncMock()
    monkeypatch.setattr(main_module, "dispose_engine", dispose_engine)

    async with main_module.lifespan(app):
        pass

    dispose_engine.assert_awaited_once_with()


async def test_create_returns_201_for_new_reservation(
    client: AsyncClient,
    service_mock: Mock,
) -> None:
    reservation = make_reservation()
    service_mock.create_reservation.return_value = ReservationResult(
        reservation=reservation,
        created=True,
    )

    response = await client.post(
        "/api/v1/reservations",
        json={"external_id": "reservation-123", "product_id": 42, "quantity": 3},
    )

    assert response.status_code == 201
    assert response.json() == {
        "external_id": "reservation-123",
        "product_id": 42,
        "quantity": 3,
        "status": "reserved",
    }


async def test_create_returns_200_for_identical_callback(
    client: AsyncClient,
    service_mock: Mock,
) -> None:
    service_mock.create_reservation.return_value = ReservationResult(
        reservation=make_reservation(),
        created=False,
    )

    response = await client.post(
        "/api/v1/reservations",
        json={"external_id": "reservation-123", "product_id": 42, "quantity": 3},
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ProductNotFoundError(42), 404),
        (InsufficientStockError(product_id=42, requested=3, available=1), 409),
        (ReservationConflictError("reservation-123"), 409),
    ],
)
async def test_create_maps_application_errors(
    client: AsyncClient,
    service_mock: Mock,
    error: Exception,
    expected_status: int,
) -> None:
    service_mock.create_reservation.side_effect = error

    response = await client.post(
        "/api/v1/reservations",
        json={"external_id": "reservation-123", "product_id": 42, "quantity": 3},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": str(error)}


@pytest.mark.parametrize("quantity", [0, -1])
async def test_create_rejects_invalid_quantity(
    client: AsyncClient,
    service_mock: Mock,
    quantity: int,
) -> None:
    response = await client.post(
        "/api/v1/reservations",
        json={
            "external_id": "reservation-123",
            "product_id": 42,
            "quantity": quantity,
        },
    )

    assert response.status_code == 422
    service_mock.create_reservation.assert_not_awaited()


async def test_get_existing_reservation(
    client: AsyncClient,
    service_mock: Mock,
) -> None:
    service_mock.get_reservation.return_value = make_reservation()

    response = await client.get("/api/v1/reservations/reservation-123")

    assert response.status_code == 200
    assert response.json()["status"] == "reserved"


async def test_get_missing_reservation(
    client: AsyncClient,
    service_mock: Mock,
) -> None:
    error = ReservationNotFoundError("missing")
    service_mock.get_reservation.side_effect = error

    response = await client.get("/api/v1/reservations/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": str(error)}
