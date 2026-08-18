from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response, status

from reservation_service.api.dependencies import ReservationServiceDependency
from reservation_service.exceptions import (
    InsufficientStockError,
    ProductNotFoundError,
    ReservationConflictError,
    ReservationNotFoundError,
)
from reservation_service.schemas import ReservationCreate, ReservationResponse

router = APIRouter(prefix="/api/v1/reservations", tags=["reservations"])


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_200_OK: {"model": ReservationResponse}},
)
async def create_reservation(
    payload: ReservationCreate,
    response: Response,
    service: ReservationServiceDependency,
) -> ReservationResponse:
    try:
        result = await service.create_reservation(payload)
    except ProductNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (InsufficientStockError, ReservationConflictError) as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error

    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return ReservationResponse.model_validate(result.reservation)


@router.get("/{external_id}", response_model=ReservationResponse)
async def get_reservation(
    external_id: Annotated[str, Path(min_length=1, max_length=255, pattern=r"\S")],
    service: ReservationServiceDependency,
) -> ReservationResponse:
    try:
        reservation = await service.get_reservation(external_id)
    except ReservationNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return ReservationResponse.model_validate(reservation)
