from pydantic import ValidationError
import pytest

from reservation_service.models import Reservation, ReservationStatus
from reservation_service.schemas import ReservationCreate, ReservationResponse


def test_valid_reservation_create_payload() -> None:
    payload = ReservationCreate(
        external_id="reservation-123",
        product_id=42,
        quantity=3,
    )

    assert payload.external_id == "reservation-123"
    assert payload.product_id == 42
    assert payload.quantity == 3


@pytest.mark.parametrize("quantity", [0, -1])
def test_reservation_quantity_must_be_positive(quantity: int) -> None:
    with pytest.raises(ValidationError):
        ReservationCreate(
            external_id="reservation-123",
            product_id=42,
            quantity=quantity,
        )


@pytest.mark.parametrize("product_id", [0, -1])
def test_product_id_must_be_positive(product_id: int) -> None:
    with pytest.raises(ValidationError):
        ReservationCreate(
            external_id="reservation-123",
            product_id=product_id,
            quantity=3,
        )


@pytest.mark.parametrize("external_id", ["", "   "])
def test_external_id_cannot_be_blank(external_id: str) -> None:
    with pytest.raises(ValidationError):
        ReservationCreate(external_id=external_id, product_id=42, quantity=3)


def test_unknown_request_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ReservationCreate.model_validate(
            {
                "external_id": "reservation-123",
                "product_id": 42,
                "quantity": 3,
                "unexpected": "value",
            }
        )


def test_response_is_created_from_orm_model() -> None:
    reservation = Reservation(
        external_id="reservation-123",
        product_id=42,
        quantity=3,
        status=ReservationStatus.RESERVED,
    )

    response = ReservationResponse.model_validate(reservation)

    assert response.model_dump(mode="json") == {
        "external_id": "reservation-123",
        "product_id": 42,
        "quantity": 3,
        "status": "reserved",
    }
