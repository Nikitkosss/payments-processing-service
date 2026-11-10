import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import session_factory
from app.infrastructure.repositories import OutboxRepository
from app.messaging.broker import broker, payments_exchange

settings = get_settings()
logger = logging.getLogger(__name__)


class OutboxRelay:
    def __init__(
        self,
        poll_interval: float | None = None,
        batch_size: int | None = None,
    ):
        self._poll_interval = poll_interval or settings.outbox_poll_interval
        self._batch_size = batch_size or settings.outbox_batch_size
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())
        logger.info("Outbox relay started")

    async def stop(self) -> None:
        if self._task is None:
            return

        self._task.cancel()

        with suppress(asyncio.CancelledError):
            await self._task

        logger.info("Outbox relay stopped")

    async def _run(self) -> None:
        while True:
            published = await self._publish_batch()

            if published == 0:
                await asyncio.sleep(self._poll_interval)

    async def _publish_batch(self) -> int:
        session = session_factory()

        try:
            repository = OutboxRepository(session)
            messages = await repository.unpublished(self._batch_size)

            if not messages:
                return 0

            for message in messages:
                body = {
                    "event_id": str(message.event_id),
                    "event_type": message.event_type,
                    "occurred_at": message.occurred_at.isoformat(),
                    "data": message.payload,
                }

                await broker.publish(
                    body,
                    exchange=payments_exchange,
                    routing_key="payment.created",
                    headers={
                        "x-event-id": str(message.event_id),
                    },
                )

                message.published_at = datetime.now(timezone.utc)

            await session.commit()

            logger.info(
                "Outbox messages published",
                extra={"count": len(messages)},
            )

            return len(messages)

        except Exception:
            await session.rollback()
            logger.exception("Failed to publish outbox messages")
            return 0

        finally:
            await session.close()
