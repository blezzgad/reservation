from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.exceptions import (
    InsufficientStockError,
    ProductNotFoundError,
    ReservationConflictError,
    ReservationNotFoundError,
)
from reservation_service.models import Reservation, ReservationStatus
from reservation_service.repositories import ProductRepository, ReservationRepository
from reservation_service.schemas import ReservationCreate


@dataclass(frozen=True, slots=True)
class ReservationResult:
    reservation: Reservation
    created: bool


class ReservationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._products = ProductRepository(session)
        self._reservations = ReservationRepository(session)

    async def create_reservation(self, payload: ReservationCreate) -> ReservationResult:
        """Reserve stock atomically and return an idempotent result."""

        # The context manager commits only after the complete operation succeeds.
        # Any application or database exception leaves through __aexit__, which
        # rolls back both the stock update and reservation insert.
        try:
            async with self._session.begin():
                return await self._create_in_transaction(payload)
        except IntegrityError:
            # UNIQUE(external_id) is the final guard for concurrent callbacks
            # that locked different Product rows.
            async with self._session.begin():
                existing = await self._reservations.get_by_external_id(payload.external_id)
                if existing is None:
                    raise
                return self._resolve_existing(existing, payload)

    async def get_reservation(self, external_id: str) -> Reservation:
        async with self._session.begin():
            reservation = await self._reservations.get_by_external_id(external_id)
            if reservation is None:
                raise ReservationNotFoundError(external_id)
            return reservation

    async def _create_in_transaction(self, payload: ReservationCreate) -> ReservationResult:
        # Fast path for ordinary callback retries: no Product lock is needed.
        existing = await self._reservations.get_by_external_id(payload.external_id)
        if existing is not None:
            return self._resolve_existing(existing, payload)

        # Requests for the same Product serialize at this row lock.
        product = await self._products.get_by_id_for_update(payload.product_id)
        if product is None:
            raise ProductNotFoundError(payload.product_id)

        # Under PostgreSQL READ COMMITTED, this statement sees a reservation
        # committed while the current request was waiting for the Product lock.
        existing = await self._reservations.get_by_external_id(payload.external_id)
        if existing is not None:
            return self._resolve_existing(existing, payload)

        # Validate before mutating the tracked ORM entity.
        if product.available_quantity < payload.quantity:
            raise InsufficientStockError(
                product_id=product.id,
                requested=payload.quantity,
                available=product.available_quantity,
            )

        # Repository.flush() sends this UPDATE and the INSERT together, while the
        # surrounding transaction still retains the option to roll both back.
        product.available_quantity -= payload.quantity
        reservation = Reservation(
            external_id=payload.external_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
            status=ReservationStatus.RESERVED,
        )
        await self._reservations.add(reservation)
        return ReservationResult(reservation=reservation, created=True)

    @staticmethod
    def _resolve_existing(
        existing: Reservation,
        payload: ReservationCreate,
    ) -> ReservationResult:
        if existing.product_id == payload.product_id and existing.quantity == payload.quantity:
            return ReservationResult(reservation=existing, created=False)
        raise ReservationConflictError(payload.external_id)
