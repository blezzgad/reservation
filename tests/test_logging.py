from collections.abc import Iterator
from uuid import UUID

from loguru import logger
import pytest
from starlette.requests import Request
from starlette.responses import Response

from reservation_service.api.middleware import (
    REQUEST_ID_HEADER,
    request_logging_middleware,
)

LogEvent = tuple[str, dict[str, object], object]


@pytest.fixture
def log_events() -> Iterator[list[LogEvent]]:
    events: list[LogEvent] = []
    sink_id = logger.add(
        lambda message: events.append(
            (
                message.record["message"],
                dict(message.record["extra"]),
                message.record["exception"],
            )
        )
    )
    yield events
    logger.remove(sink_id)


def make_request(*, request_id: str | None = None, path: str = "/health") -> Request:
    headers = [] if request_id is None else [(b"x-request-id", request_id.encode())]
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("test", 80),
        }
    )


async def successful_handler(_: Request) -> Response:
    return Response(status_code=204)


async def failing_handler(_: Request) -> Response:
    raise RuntimeError("database credentials must not appear in response")


async def test_existing_request_id_is_reused(log_events: list[LogEvent]) -> None:
    response = await request_logging_middleware(
        make_request(request_id="upstream-request-id"),
        successful_handler,
    )

    assert response.headers[REQUEST_ID_HEADER] == "upstream-request-id"
    completion = next(event for event in log_events if event[0] == "request completed")
    assert completion[1]["request_id"] == "upstream-request-id"
    assert completion[1]["method"] == "GET"
    assert completion[1]["path"] == "/health"
    assert completion[1]["status_code"] == 204
    assert isinstance(completion[1]["duration_ms"], float)


async def test_request_id_is_generated_when_missing() -> None:
    response = await request_logging_middleware(make_request(), successful_handler)

    UUID(response.headers[REQUEST_ID_HEADER])


async def test_unexpected_error_is_logged_and_hidden(log_events: list[LogEvent]) -> None:
    response = await request_logging_middleware(
        make_request(path="/failing"),
        failing_handler,
    )

    assert response.status_code == 500
    assert response.body == b'{"detail":"Internal server error"}'
    assert REQUEST_ID_HEADER in response.headers
    error_event = next(event for event in log_events if event[0] == "unexpected error")
    assert error_event[2] is not None
