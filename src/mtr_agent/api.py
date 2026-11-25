"""HTTP transport with optional bearer auth, bounded admission and private metrics."""

import hmac
import logging
import os
import threading
import time
import uuid
from collections import Counter

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from . import __version__
from .agent import Agent
from .models import ChatRequest

logger = logging.getLogger(__name__)


def create_app(agent=None, api_key: str | None = None, max_inflight: int = 32) -> FastAPI:
    if max_inflight < 1:
        raise ValueError("max_inflight must be positive")
    service = agent or Agent()
    secret = os.environ.get("MTR_API_KEY", "") if api_key is None else api_key
    app = FastAPI(title="MTR Polyglot Agent", version=__version__,
                  description="Synthetic metro Agent portfolio; not live travel advice.")
    app.state.agent = service
    counts = Counter()
    metrics_lock = threading.Lock()
    admission = threading.BoundedSemaphore(max_inflight)

    @app.middleware("http")
    async def request_boundary(request: Request, call_next):
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        path = request.url.path
        if secret and path != "/health":
            supplied = request.headers.get("authorization", "")
            if not hmac.compare_digest(supplied.encode(), ("Bearer " + secret).encode()):
                return JSONResponse({"detail": "Unauthorized", "request_id": request_id},
                                    status_code=401, headers={"X-Request-ID": request_id})
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 16384:
            return JSONResponse({"detail": "Request body too large"}, status_code=413,
                                headers={"X-Request-ID": request_id})
        if not admission.acquire(blocking=False):
            return JSONResponse({"detail": "Server busy"}, status_code=503,
                                headers={"Retry-After": "1", "X-Request-ID": request_id})
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            with metrics_lock:
                counts["requests"] += 1
                counts[f"status_{response.status_code}"] += 1
                counts["duration_ms"] += (time.perf_counter() - started) * 1000
            logger.info("request_complete id=%s status=%s", request_id, response.status_code)
            return response
        finally:
            admission.release()

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/ready")
    def ready():
        return {"status": "ready", "knowledge_version": service.kb.version,
                "mode": "llm-assisted" if service.llm else "offline"}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics():
        with metrics_lock:
            snapshot = dict(counts)
        return (f"mtr_requests_total {snapshot.get('requests', 0)}\n"
                f"mtr_request_duration_ms_sum {snapshot.get('duration_ms', 0):.3f}\n"
                f"mtr_sessions {len(service.sessions)}\n"
                f"mtr_redis_errors_total {service.tools.cache.redis_errors}\n")

    @app.post("/v1/chat")
    def chat(payload: ChatRequest, request: Request):
        result = service.chat(payload.message, payload.session_id)
        result["request_id"] = request.state.request_id
        return result

    @app.delete("/v1/sessions/{session_id}")
    def delete_session(session_id: str):
        return {"deleted": service.delete_session(session_id)}

    @app.get("/v1/tools")
    def tool_schemas():
        return {"tools": service.tools.schemas()}

    @app.post("/v1/tools/{name}")
    def tool_call(name: str, arguments: dict = Body(...)):
        try:
            return service.tools.call(name, arguments)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app
