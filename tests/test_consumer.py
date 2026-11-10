from unittest.mock import AsyncMock

import pytest

from app.messaging import consumer as consumer_module


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("header_attempts", "routing_key"),
    [
        (None, "payment.retry.1"),
        (0, "payment.retry.1"),
        (1, "payment.retry.2"),
        (2, "payment.retry.3"),
        (3, "payment.dead"),
    ],
)
async def test_retry_or_dead_letter_routing(monkeypatch, header_attempts, routing_key):
    publish = AsyncMock()
    monkeypatch.setattr(consumer_module.broker, "publish", publish)

    headers = {}
    if header_attempts is not None:
        headers["x-attempts"] = header_attempts

    await consumer_module.retry_or_dead_letter(
        {"data": {"payment_id": "x"}},
        headers,
        "boom",
    )

    publish.assert_awaited_once()
    kwargs = publish.await_args.kwargs
    assert kwargs["routing_key"] == routing_key
    expected_attempts = 1 if header_attempts is None else header_attempts + 1
    assert kwargs["headers"]["x-attempts"] == expected_attempts
    assert kwargs["headers"]["x-error"] == "boom"
