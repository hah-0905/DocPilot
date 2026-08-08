import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response


logger = logging.getLogger(__name__)


async def request_log_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    request.state.request_id = request_id

    try:
        response = await call_next(request)

    except Exception:
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        logger.exception(
            "Request failed | request_id=%s method=%s path=%s latency_ms=%s",
            request_id,
            request.method,
            request.url.path,
            latency_ms,
        )

        raise

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    logger.info(
        "Request completed | request_id=%s method=%s path=%s status_code=%s latency_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        latency_ms,
    )

    response.headers["X-Request-ID"] = request_id

    return response