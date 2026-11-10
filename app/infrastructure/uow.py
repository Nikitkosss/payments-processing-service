from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import session_factory
from app.infrastructure.repositories import OutboxRepository, PaymentRepository


class AbstractUnitOfWork(ABC):
    session: AsyncSession
    payments: PaymentRepository
    outbox: OutboxRepository

    @abstractmethod
    async def __aenter__(self):
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb):
        raise NotImplementedError

    @abstractmethod
    async def commit(self):
        raise NotImplementedError

    async def rollback(self) -> None:
        await self.session.rollback()


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory=session_factory):
        self._session_factory = session_factory

    async def __aenter__(self):
        self.session = self._session_factory()

        self.payments = PaymentRepository(self.session)
        self.outbox = OutboxRepository(self.session)

        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if exc_type is not None:
                await self.session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()
