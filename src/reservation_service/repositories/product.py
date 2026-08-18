from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id_for_update(self, product_id: int) -> Product | None:
        """Return a product while locking its row until transaction end."""

        statement = select(Product).where(Product.id == product_id).with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
