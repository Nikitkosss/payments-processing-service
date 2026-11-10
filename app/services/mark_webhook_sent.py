from uuid import UUID

from app.infrastructure.uow import SqlAlchemyUnitOfWork


class MarkWebhookSentUseCase:
    def __init__(self, uow_factory=SqlAlchemyUnitOfWork):
        self._uow_factory = uow_factory

    async def execute(self, payment_id: UUID) -> bool:
        async with self._uow_factory() as uow:
            changed = await uow.payments.mark_webhook_sent(payment_id)
            await uow.commit()
            return changed
