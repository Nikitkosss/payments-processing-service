import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.routers import router
from app.core.config import get_settings
from app.core.logging import setup_logging, trace_id_var
from app.messaging.broker import broker
from app.messaging.outbox_relay import OutboxRelay
from app.messaging.topology import declare_rabbit_topology

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(
        level=settings.log_level,
        json_logs=settings.log_json,
    )

    await declare_rabbit_topology()
    await broker.start()

    relay = OutboxRelay(
        poll_interval=settings.outbox_poll_interval,
        batch_size=settings.outbox_batch_size,
    )

    await relay.start()

    yield

    await relay.stop()
    await broker.stop()


app = FastAPI(
    title="Payments Processing Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.middleware("http")
async def set_trace_id(request: Request, call_next):
    trace_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = trace_id_var.set(trace_id)

    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        return response
    finally:
        trace_id_var.reset(token)


@app.get("/health")
async def health():
    return {
        "status": "ok",
    }
