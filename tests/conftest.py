import os

os.environ["API_KEY"] = "test-api-key"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_payments.db"
os.environ["RABBIT_URL"] = "amqp://guest:guest@localhost:5672//"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["LOG_JSON"] = "false"

from unittest.mock import AsyncMock, patch

_patches = [
    patch(
        "app.messaging.topology.declare_rabbit_topology",
        new_callable=AsyncMock,
    ),
    patch("app.messaging.broker.broker.start", new_callable=AsyncMock),
    patch("app.messaging.broker.broker.stop", new_callable=AsyncMock),
    patch("app.messaging.outbox_relay.OutboxRelay.start", new_callable=AsyncMock),
    patch("app.messaging.outbox_relay.OutboxRelay.stop", new_callable=AsyncMock),
]

for item in _patches:
    item.start()

from app.api.main import app  # noqa: E402

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.models import Base
from app.db.session import engine


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def cleanup_engine():
    yield
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as async_client:
        yield async_client
