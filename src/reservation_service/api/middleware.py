from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import status
from loguru import logger
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

RequestHandler = Callable[[Request], Awaitable[Response]]

REQUEST_ID_HEADER = "X-Request-ID"


async def request_logging_middleware(
    request: Request,
    call_next: RequestHandler,
) -> Response:
    # Preserve the caller's correlation id across service boundaries. A UUID is
    # generated only when the upstream service did not provide one.
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
    # State makes the id available to later HTTP dependencies without coupling
    # them to Loguru.
    request.state.request_id = request_id
    started_at = perf_counter()

    # contextualize uses contextvars, so concurrent requests cannot overwrite
    # each other's request_id while awaiting database or network operations.
    with logger.contextualize(request_id=request_id):
        try:
            response = await call_next(request)
        except Exception:
            # Keep the stack trace in logs but never expose exception details,
            # SQL, or credentials to the external caller.
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            logger.bind(
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            ).exception("unexpected error")
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"},
            )

        # Both successful and failed responses follow the same completion-log
        # and response-header path.
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.bind(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        ).info("request completed")
        return response
