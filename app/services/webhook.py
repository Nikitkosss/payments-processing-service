import logging

import httpx

from app.core.config import get_settings
from app.db.models import Payment
from app.domain.exceptions import WebhookDeliveryError

settings = get_settings()
logger = logging.getLogger(__name__)


class WebhookSender:
    def __init__(self, timeout: float | None = None):
        self._timeout = timeout or settings.webhook_timeout

    async def send(self, payment: Payment) -> None:
        payload = {
            "event": "payment.finished",
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "amount": str(payment.amount),
            "currency": payment.currency.value,
            "description": payment.description,
            "metadata": payment.metadata_,
            "created_at": payment.created_at.isoformat(),
            "processed_at": (
                payment.processed_at.isoformat()
                if payment.processed_at
                else None
            ),
        }

        headers = {
            "Content-Type": "application/json",
            "X-Event-Type": "payment.finished",
            "X-Payment-Id": str(payment.id),
        }

        logger.info(
            "Sending webhook",
            extra={
                "payment_id": str(payment.id),
                "webhook_url": payment.webhook_url,
            },
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    payment.webhook_url,
                    json=payload,
                    headers=headers,
                )

                if response.status_code >= 400:
                    raise WebhookDeliveryError(
                        f"Webhook returned HTTP {response.status_code}",
                    )

        except httpx.HTTPError as exc:
            raise WebhookDeliveryError(str(exc)) from exc

        logger.info(
            "Webhook delivered",
            extra={"payment_id": str(payment.id)},
        )
