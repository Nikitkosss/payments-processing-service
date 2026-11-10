from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OutboxMessage, Payment
from app.domain.enums import PaymentStatus


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def add(self, payment: Payment) -> None:
        self._session.add(payment)

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        return await self._session.get(Payment, payment_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> Payment | None:
        stmt = select(Payment).where(
            Payment.idempotency_key == idempotency_key,
        )
        return await self._session.scalar(stmt)

    async def complete_processing(
        self,
        payment_id: UUID,
        status: PaymentStatus,
    ) -> Payment | None:
        """
        Обновляем платёж только если он ещё в статусе pending.

        Это защищает от повторной обработки при повторной доставке сообщения.
        """
        stmt = (
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.status == PaymentStatus.PENDING,
            )
            .values(
                status=status,
                processed_at=func.now(),
            )
            .returning(Payment)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_webhook_sent(self, payment_id: UUID) -> bool:
        """
        Отмечаем, что вебхук отправлен.

        Обновляем только если webhook_sent_at IS NULL.
        Это делает отправку вебхука идемпотентной.
        """
        stmt = (
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.webhook_sent_at.is_(None),
            )
            .values(webhook_sent_at=func.now())
            .returning(Payment.id)
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None


class OutboxRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def add(self, message: OutboxMessage) -> None:
        self._session.add(message)

    async def unpublished(self, limit: int) -> list[OutboxMessage]:
        """
        Выбираем неопубликованные события.

        FOR UPDATE SKIP LOCKED позволяет запускать несколько
        outbox relay параллельно.
        """
        stmt = (
            select(OutboxMessage)
            .where(OutboxMessage.published_at.is_(None))
            .order_by(OutboxMessage.occurred_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())
