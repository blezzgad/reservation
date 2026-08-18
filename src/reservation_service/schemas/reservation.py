from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from reservation_service.models.reservation import ReservationStatus

ExternalId = Annotated[str, Field(min_length=1, max_length=255, pattern=r"\S")]


class ReservationCreate(BaseModel):
    """Payload accepted when an external service requests a reservation."""

    model_config = ConfigDict(extra="forbid")

    external_id: ExternalId
    product_id: PositiveInt
    quantity: PositiveInt


class ReservationResponse(BaseModel):
    """Public representation of a successful reservation."""

    model_config = ConfigDict(from_attributes=True)

    external_id: str
    product_id: int
    quantity: int
    status: ReservationStatus
