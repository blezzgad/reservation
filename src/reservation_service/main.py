from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from reservation_service.api.v1.reservations import router as reservations_router
from reservation_service.db.session import dispose_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await dispose_engine()


app = FastAPI(
    title="Reservation Service",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(reservations_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
