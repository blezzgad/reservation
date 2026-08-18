"""Create products and reservations tables.

Revision ID: 0001
Revises:
Create Date: 2026-08-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

reservation_status = postgresql.ENUM(
    "reserved",
    name="reservation_status",
    create_type=False,
)


def upgrade() -> None:
    """Create the initial reservation schema."""

    postgresql.ENUM("reserved", name="reservation_status").create(
        op.get_bind(),
        checkfirst=True,
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=255), nullable=False),
        sa.Column("available_quantity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "available_quantity >= 0",
            name="ck_products_available_quantity_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
    )

    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            reservation_status,
            server_default=sa.text("'reserved'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="ck_reservations_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_reservations_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_reservations_external_id"),
    )


def downgrade() -> None:
    """Remove the initial reservation schema."""

    op.drop_table("reservations")
    op.drop_table("products")
    reservation_status.drop(op.get_bind(), checkfirst=True)
