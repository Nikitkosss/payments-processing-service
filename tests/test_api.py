from uuid import uuid4

import pytest


def make_payload() -> dict:
    return {
        "amount": "100.50",
        "currency": "RUB",
        "description": "Test payment",
        "metadata": {
            "order_id": "order-1",
        },
        "webhook_url": "https://example.com/webhook",
    }


@pytest.mark.asyncio
async def test_missing_api_key(client):
    response = await client.post(
        "/api/v1/payments",
        headers={
            "Idempotency-Key": str(uuid4()),
        },
        json=make_payload(),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_api_key(client):
    response = await client.post(
        "/api/v1/payments",
        headers={
            "X-API-Key": "wrong-api-key",
            "Idempotency-Key": str(uuid4()),
        },
        json=make_payload(),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_idempotency_key(client):
    response = await client.post(
        "/api/v1/payments",
        headers={
            "X-API-Key": "test-api-key",
        },
        json=make_payload(),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_payment_and_idempotency(client):
    idempotency_key = str(uuid4())

    headers = {
        "X-API-Key": "test-api-key",
        "Idempotency-Key": idempotency_key,
    }

    payload = make_payload()

    first_response = await client.post(
        "/api/v1/payments",
        headers=headers,
        json=payload,
    )

    assert first_response.status_code == 202

    first_data = first_response.json()

    assert first_data["payment_id"]
    assert first_data["status"] == "pending"
    assert first_data["created_at"]

    second_response = await client.post(
        "/api/v1/payments",
        headers=headers,
        json=payload,
    )

    assert second_response.status_code == 202

    second_data = second_response.json()

    assert second_data["payment_id"] == first_data["payment_id"]


@pytest.mark.asyncio
async def test_get_payment(client):
    idempotency_key = str(uuid4())

    headers = {
        "X-API-Key": "test-api-key",
        "Idempotency-Key": idempotency_key,
    }

    payload = make_payload()

    create_response = await client.post(
        "/api/v1/payments",
        headers=headers,
        json=payload,
    )

    assert create_response.status_code == 202

    payment_id = create_response.json()["payment_id"]

    get_response = await client.get(
        f"/api/v1/payments/{payment_id}",
        headers={
            "X-API-Key": "test-api-key",
        },
    )

    assert get_response.status_code == 200

    data = get_response.json()

    assert data["id"] == payment_id
    assert data["status"] == "pending"
    assert data["description"] == "Test payment"
    assert data["metadata"] == {"order_id": "order-1"}
    assert data["webhook_url"] == "https://example.com/webhook"


@pytest.mark.asyncio
async def test_get_payment_not_found(client):
    response = await client.get(
        f"/api/v1/payments/{uuid4()}",
        headers={
            "X-API-Key": "test-api-key",
        },
    )

    assert response.status_code == 404
