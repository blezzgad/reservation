from typing import Never

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from reservation_service.exceptions import (
    ProductInUseError,
    ProductNotFoundError,
    ProductSkuConflictError,
)
from reservation_service.models import Product
from reservation_service.repositories import ProductRepository, ReservationRepository
from reservation_service.schemas import ProductCreate


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._products = ProductRepository(session)
        self._reservations = ReservationRepository(session)

    async def create_product(self, payload: ProductCreate) -> Product:
        # The preliminary lookup gives ordinary duplicate requests a clear error.
        # It is not the concurrency guarantee: two transactions may both see None.
        try:
            async with self._session.begin():
                existing = await self._products.get_by_sku(payload.sku)
                if existing is not None:
                    raise ProductSkuConflictError(payload.sku)

                product = Product(
                    sku=payload.sku,
                    available_quantity=payload.available_quantity,
                )
                await self._products.add(product)
        except IntegrityError as error:
            # UNIQUE(sku) is the final guard for concurrent product creation. Read
            # the winner after rollback, but never hide an unrelated constraint error.
            async with self._session.begin():
                existing = await self._products.get_by_sku(payload.sku)
            if existing is not None:
                raise ProductSkuConflictError(payload.sku) from error
            raise

        logger.bind(
            product_id=product.id,
            sku=product.sku,
            available_quantity=product.available_quantity,
        ).info("product created")
        return product

    async def delete_product(self, product_id: int) -> None:
        # Reservation creation uses the same Product row lock, so deletion cannot
        # pass while a reservation for this Product is being committed.
        try:
            async with self._session.begin():
                product = await self._products.get_by_id_for_update(product_id)
                if product is None:
                    raise ProductNotFoundError(product_id)
                if await self._reservations.exists_for_product(product_id):
                    self._raise_product_in_use(product_id)

                sku = product.sku
                await self._products.delete(product)
        except IntegrityError as error:
            # FK RESTRICT is still authoritative if a writer bypasses this service.
            # Confirm the reason after rollback before mapping it to ProductInUse.
            async with self._session.begin():
                in_use = await self._reservations.exists_for_product(product_id)
            if in_use:
                raise ProductInUseError(product_id) from error
            raise

        logger.bind(product_id=product_id, sku=sku).info("product deleted")

    @staticmethod
    def _raise_product_in_use(product_id: int) -> Never:
        logger.bind(product_id=product_id).warning("product deletion rejected")
        raise ProductInUseError(product_id)
