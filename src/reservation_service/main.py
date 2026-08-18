from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from reservation_service.api.middleware import request_logging_middleware
from reservation_service.api.v1.reservations import router as reservations_router
from reservation_service.core.config import get_settings
from reservation_service.core.logging import configure_logging
from reservation_service.db.session import dispose_engine

configure_logging(get_settings().log_level)


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
app.middleware("http")(request_logging_middleware)
app.include_router(reservations_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
