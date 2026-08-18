from typing import cast

from sqlalchemy import CheckConstraint, DateTime, Enum, Table, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from reservation_service.models import Product, Reservation, ReservationStatus


def test_model_relationships_are_configured() -> None:
    configure_mappers()

    assert Product.reservations.property.back_populates == "product"
    assert Reservation.product.property.back_populates == "reservations"


def test_product_database_constraints() -> None:
    constraints = cast(Table, Product.__table__).constraints

    assert any(
        isinstance(constraint, UniqueConstraint) and constraint.name == "uq_products_sku"
        for constraint in constraints
    )
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_products_available_quantity_nonnegative"
        for constraint in constraints
    )


def test_reservation_database_constraints() -> None:
    constraints = cast(Table, Reservation.__table__).constraints

    assert any(
        isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_reservations_external_id"
        for constraint in constraints
    )
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_reservations_quantity_positive"
        for constraint in constraints
    )


def test_timestamps_are_timezone_aware() -> None:
    timestamp_columns = (
        Product.created_at,
        Product.updated_at,
        Reservation.created_at,
        Reservation.updated_at,
    )

    assert all(
        isinstance(column.property.columns[0].type, DateTime)
        and column.property.columns[0].type.timezone
        for column in timestamp_columns
    )


def test_reservation_status_uses_enum_values() -> None:
    status_type = Reservation.__table__.c.status.type

    assert isinstance(status_type, Enum)
    assert status_type.enums == [ReservationStatus.RESERVED.value]
