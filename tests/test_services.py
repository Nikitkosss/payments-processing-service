from decimal import Decimal
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock

from app.db.session import session_factory
from app.domain.enums import Currency, PaymentStatus
from app.infrastructure.uow import SqlAlchemyUnitOfWork
from app.services.create_payment import CreatePaymentCommand, CreatePaymentUseCase
from app.services.process_payment import ProcessPaymentUseCase
import app.services.process_payment as process_payment_module


@pytest.fixture
def uow_factory():
    return lambda: SqlAlchemyUnitOfWork(session_factory)


async def create_payment(uow_factory) -> str:
    use_case = CreatePaymentUseCase(uow_factory)

    command = CreatePaymentCommand(
        idempotency_key=str(uuid4()),
        amount=Decimal("99.99"),
        currency=Currency.RUB,
        description="Service test",
        metadata={"source": "test"},
        webhook_url="https://example.com/webhook",
    )

    payment = await use_case.execute(command)
    return payment.id


@pytest.mark.asyncio
async def test_create_payment_use_case(uow_factory):
    use_case = CreatePaymentUseCase(uow_factory)

    command = CreatePaymentCommand(
        idempotency_key=str(uuid4()),
        amount=Decimal("10.00"),
        currency=Currency.USD,
        description="Test",
        metadata={},
        webhook_url="https://example.com/webhook",
    )

    payment = await use_case.execute(command)

    assert payment.id
    assert payment.status == PaymentStatus.PENDING


@pytest.mark.asyncio
async def test_create_payment_idempotency_in_service(uow_factory):
    use_case = CreatePaymentUseCase(uow_factory)

    command = CreatePaymentCommand(
        idempotency_key=str(uuid4()),
        amount=Decimal("10.00"),
        currency=Currency.EUR,
        description="Test",
        metadata={},
        webhook_url="https://example.com/webhook",
    )

    first = await use_case.execute(command)
    second = await use_case.execute(command)

    assert first.id == second.id


@pytest.mark.asyncio
async def test_process_payment_success(uow_factory, monkeypatch):
    payment_id = await create_payment(uow_factory)

    monkeypatch.setattr(
        process_payment_module.asyncio,
        "sleep",
        AsyncMock(return_value=None),
    )

    monkeypatch.setattr(
        process_payment_module.random,
        "random",
        lambda: 0.1,
    )

    use_case = ProcessPaymentUseCase(uow_factory)
    payment = await use_case.execute(payment_id)

    assert payment.status == PaymentStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_process_payment_failure(uow_factory, monkeypatch):
    payment_id = await create_payment(uow_factory)

    monkeypatch.setattr(
        process_payment_module.asyncio,
        "sleep",
        AsyncMock(return_value=None),
    )

    monkeypatch.setattr(
        process_payment_module.random,
        "random",
        lambda: 0.95,
    )

    use_case = ProcessPaymentUseCase(uow_factory)
    payment = await use_case.execute(payment_id)

    assert payment.status == PaymentStatus.FAILED
