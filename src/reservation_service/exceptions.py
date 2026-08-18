class ReservationServiceError(Exception):
    """Base class for expected reservation application errors."""


class ProductNotFoundError(ReservationServiceError):
    def __init__(self, product_id: int) -> None:
        self.product_id = product_id
        super().__init__(f"Product with id {product_id} was not found")


class ReservationNotFoundError(ReservationServiceError):
    def __init__(self, external_id: str) -> None:
        self.external_id = external_id
        super().__init__(f"Reservation with external_id {external_id!r} was not found")


class InsufficientStockError(ReservationServiceError):
    def __init__(self, product_id: int, requested: int, available: int) -> None:
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for product {product_id}: "
            f"requested {requested}, available {available}"
        )


class ReservationConflictError(ReservationServiceError):
    def __init__(self, external_id: str) -> None:
        self.external_id = external_id
        super().__init__(
            f"Reservation with external_id {external_id!r} already exists with different parameters"
        )
