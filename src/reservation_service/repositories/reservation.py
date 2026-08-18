from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.models.reservation import Reservation


class ReservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_external_id(self, external_id: str) -> Reservation | None:
        statement = select(Reservation).where(Reservation.external_id == external_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def exists_for_product(self, product_id: int) -> bool:
        statement = select(exists().where(Reservation.product_id == product_id))
        result = await self._session.execute(statement)
        return bool(result.scalar_one())

    async def add(self, reservation: Reservation) -> None:
        """Add and flush a reservation without committing the transaction."""

        self._session.add(reservation)
        await self._session.flush()
