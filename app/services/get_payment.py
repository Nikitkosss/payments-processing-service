from uuid import UUID

from app.db.models import Payment
from app.infrastructure.uow import AbstractUnitOfWork, SqlAlchemyUnitOfWork


class GetPaymentUseCase:
    def __init__(self, uow_factory):
        self._uow_factory = uow_factory

    async def execute(self, payment_id: UUID) -> Payment | None:
        async with self._uow_factory() as uow:
            return await uow.payments.get_by_id(payment_id)
