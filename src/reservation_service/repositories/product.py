from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_sku(self, sku: str) -> Product | None:
        # This lookup is only an early conflict check; UNIQUE(sku) remains the
        # concurrency guarantee, so no row lock is required here.
        statement = select(Product).where(Product.sku == sku)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, product_id: int) -> Product | None:
        """Return a product while locking its row until transaction end."""

        statement = select(Product).where(Product.id == product_id).with_for_update()
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def add(self, product: Product) -> None:
        # Flush surfaces constraints but leaves commit/rollback to the service.
        self._session.add(product)
        await self._session.flush()

    async def delete(self, product: Product) -> None:
        # FK RESTRICT failures must occur inside the service transaction.
        await self._session.delete(product)
        await self._session.flush()
