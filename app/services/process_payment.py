import asyncio
import logging
import random
from uuid import UUID

from app.db.models import Payment
from app.domain.enums import PaymentStatus
from app.domain.exceptions import PaymentNotFoundError
from app.infrastructure.uow import SqlAlchemyUnitOfWork

logger = logging.getLogger(__name__)


class ProcessPaymentUseCase:
    def __init__(self, uow_factory=SqlAlchemyUnitOfWork):
        self._uow_factory = uow_factory

    async def execute(self, payment_id: UUID) -> Payment:
        async with self._uow_factory() as uow:
            payment = await uow.payments.get_by_id(payment_id)

            if payment is None:
                raise PaymentNotFoundError(payment_id)

            if payment.status is not PaymentStatus.PENDING:
                logger.info(
                    "Payment already processed",
                    extra={
                        "payment_id": str(payment.id),
                        "status": payment.status.value,
                    },
                )
                return payment

        # Симуляция внешней обработки.
        # Не держим транзакцию открытой во время сна.
        await asyncio.sleep(random.uniform(2.0, 5.0))

        new_status = (
            PaymentStatus.SUCCEEDED
            if random.random() < 0.90
            else PaymentStatus.FAILED
        )

        logger.info(
            "Simulated payment processing finished",
            extra={
                "payment_id": str(payment_id),
                "new_status": new_status.value,
            },
        )

        async with self._uow_factory() as uow:
            updated_payment = await uow.payments.complete_processing(
                payment_id=payment_id,
                status=new_status,
            )

            if updated_payment is None:
                payment = await uow.payments.get_by_id(payment_id)

                if payment is None:
                    raise PaymentNotFoundError(payment_id)

                return payment

            await uow.commit()
            return updated_payment
