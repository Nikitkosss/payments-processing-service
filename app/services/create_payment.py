import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.db.models import OutboxMessage, Payment
from app.domain.enums import Currency
from app.infrastructure.uow import AbstractUnitOfWork, SqlAlchemyUnitOfWork

logger = logging.getLogger(__name__)

PAYMENT_EVENT_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")


@dataclass(slots=True)
class CreatePaymentCommand:
    idempotency_key: str
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict
    webhook_url: str


class CreatePaymentUseCase:
    def __init__(self, uow_factory):
        self._uow_factory = uow_factory

    async def execute(self, command: CreatePaymentCommand) -> Payment:
        logger.info(
            "Creating payment",
            extra={"idempotency_key": command.idempotency_key},
        )

        async with self._uow_factory() as uow:
            existing = await uow.payments.get_by_idempotency_key(
                command.idempotency_key,
            )

            if existing is not None:
                logger.info(
                    "Payment already exists",
                    extra={
                        "payment_id": str(existing.id),
                        "idempotency_key": command.idempotency_key,
                    },
                )
                return existing

            payment = Payment(
                id=uuid.uuid4(),
                amount=command.amount,
                currency=command.currency,
                description=command.description,
                metadata_=command.metadata,
                idempotency_key=command.idempotency_key,
                webhook_url=str(command.webhook_url),
            )

            event = OutboxMessage(
                id=uuid.uuid4(),
                event_id=uuid.uuid5(
                    PAYMENT_EVENT_NAMESPACE,
                    f"payment.created:{payment.id}",
                ),
                aggregate_id=payment.id,
                event_type="payment.created",
                payload={
                    "payment_id": str(payment.id),
                    "amount": str(payment.amount),
                    "currency": payment.currency.value,
                    "description": payment.description,
                    "metadata": payment.metadata_,
                    "webhook_url": payment.webhook_url,
                    "idempotency_key": payment.idempotency_key,
                },
            )

            uow.payments.add(payment)
            uow.outbox.add(event)

            try:
                await uow.commit()
            except IntegrityError:
                await uow.rollback()

                logger.warning(
                    "Idempotency conflict while creating payment",
                    extra={"idempotency_key": command.idempotency_key},
                )

                async with self._uow_factory() as retry_uow:
                    existing = await retry_uow.payments.get_by_idempotency_key(
                        command.idempotency_key,
                    )

                    if existing is None:
                        raise

                    return existing

            logger.info(
                "Payment created",
                extra={"payment_id": str(payment.id)},
            )

            return payment
