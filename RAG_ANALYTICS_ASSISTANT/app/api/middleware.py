
import uuid
import time
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from app.utils.logger import get_logger, log_event

log = get_logger(__name__)


def add_middleware(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.time()
        response = await call_next(request)
        latency = int((time.time() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        log_event(log, "info", "request_handled",
                  method=request.method,
                  path=request.url.path,
                  status=response.status_code,
                  latency_ms=latency,
                  request_id=request_id)
        return response