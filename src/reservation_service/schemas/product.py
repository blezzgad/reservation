from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

Sku = Annotated[str, Field(min_length=1, max_length=255, pattern=r"\S")]


class ProductCreate(BaseModel):
    """Payload used to add reservable stock."""

    model_config = ConfigDict(extra="forbid")

    sku: Sku
    available_quantity: NonNegativeInt


class ProductResponse(BaseModel):
    """Public product representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    available_quantity: int
    created_at: datetime
    updated_at: datetime
