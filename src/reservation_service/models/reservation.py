from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from reservation_service.db.base import Base

if TYPE_CHECKING:
    from reservation_service.models.product import Product


class ReservationStatus(StrEnum):
    RESERVED = "reserved"


class Reservation(Base):
    """A successful product reservation requested by an external service."""

    __tablename__ = "reservations"
    __table_args__ = (
        UniqueConstraint("external_id", name="uq_reservations_external_id"),
        CheckConstraint("quantity > 0", name="ck_reservations_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey(
            "products.id",
            name="fk_reservations_product_id_products",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(
            ReservationStatus,
            name="reservation_status",
            values_callable=lambda statuses: [status.value for status in statuses],
            validate_strings=True,
        ),
        nullable=False,
        default=ReservationStatus.RESERVED,
        server_default=ReservationStatus.RESERVED.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    product: Mapped["Product"] = relationship(back_populates="reservations")
