from reservation_service.exceptions import (
    InsufficientStockError,
    ProductNotFoundError,
    ReservationConflictError,
    ReservationNotFoundError,
    ReservationServiceError,
)


def test_product_not_found_error_keeps_product_id() -> None:
    error = ProductNotFoundError(product_id=42)

    assert isinstance(error, ReservationServiceError)
    assert error.product_id == 42
    assert str(error) == "Product with id 42 was not found"


def test_reservation_not_found_error_keeps_external_id() -> None:
    error = ReservationNotFoundError(external_id="reservation-123")

    assert error.external_id == "reservation-123"
    assert "reservation-123" in str(error)


def test_insufficient_stock_error_keeps_stock_context() -> None:
    error = InsufficientStockError(product_id=42, requested=4, available=1)

    assert error.product_id == 42
    assert error.requested == 4
    assert error.available == 1


def test_reservation_conflict_error_keeps_external_id() -> None:
    error = ReservationConflictError(external_id="reservation-123")

    assert error.external_id == "reservation-123"
    assert "different parameters" in str(error)
