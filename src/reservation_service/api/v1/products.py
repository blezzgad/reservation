from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response, status

from reservation_service.api.dependencies import ProductServiceDependency
from reservation_service.exceptions import (
    ProductInUseError,
    ProductNotFoundError,
    ProductSkuConflictError,
)
from reservation_service.schemas import ProductCreate, ProductResponse

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    service: ProductServiceDependency,
) -> ProductResponse:
    try:
        product = await service.create_product(payload)
    except ProductSkuConflictError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: Annotated[int, Path(gt=0)],
    service: ProductServiceDependency,
) -> Response:
    try:
        await service.delete_product(product_id)
    except ProductNotFoundError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ProductInUseError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
