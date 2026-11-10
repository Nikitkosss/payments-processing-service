import logging
from uuid import UUID

from faststream.rabbit import RabbitMessage

from app.core.config import get_settings
from app.core.logging import trace_id_var
from app.domain.exceptions import PaymentNotFoundError
from app.messaging.broker import broker, new_queue, payments_exchange
from app.services.mark_webhook_sent import MarkWebhookSentUseCase
from app.services.process_payment import ProcessPaymentUseCase
from app.services.webhook import WebhookSender

settings = get_settings()
logger = logging.getLogger(__name__)

process_payment_use_case = ProcessPaymentUseCase()
mark_webhook_sent_use_case = MarkWebhookSentUseCase()
webhook_sender = WebhookSender()


async def retry_or_dead_letter(
    payload: dict,
    headers: dict,
    reason: str,
) -> None:
    attempts = int(headers.get("x-attempts", 0))
    next_attempt = attempts + 1

    if next_attempt <= settings.max_delivery_attempts:
        queue_name = f"payments.retry.{next_attempt}"

        await broker.publish(
            payload,
            exchange=payments_exchange,
            routing_key=f"payment.retry.{next_attempt}",
            headers={
                **headers,
                "x-attempts": next_attempt,
                "x-error": reason,
            },
        )

        logger.warning(
            "Payment event retry scheduled",
            extra={
                "queue": queue_name,
                "attempt": next_attempt,
                "reason": reason,
            },
        )

        return

    await broker.publish(
        payload,
        exchange=payments_exchange,
        routing_key="payment.dead",
        headers={
            **headers,
            "x-attempts": next_attempt,
            "x-error": reason,
        },
    )

    logger.error(
        "Payment event moved to DLQ",
        extra={
            "attempt": next_attempt,
            "reason": reason,
        },
    )


@broker.subscriber(queue=new_queue, exchange=payments_exchange)
async def handle_payment_created(
    payload: dict,
    message: RabbitMessage,
) -> None:
    headers = dict(getattr(message, "headers", None) or {})
    trace_id_var.set(payload.get("event_id"))

    try:
        payment_id = UUID(payload["data"]["payment_id"])
        payment = await process_payment_use_case.execute(payment_id)

    except PaymentNotFoundError:
        logger.error("Payment not found while consuming event")

        await broker.publish(
            payload,
            exchange=payments_exchange,
            routing_key="payment.dead",
            headers={
                **headers,
                "x-error": "payment-not-found",
            },
        )
        return

    except Exception as exc:
        logger.exception("Failed to process payment event")
        await retry_or_dead_letter(payload, headers, str(exc))
        return

    try:
        if payment.webhook_sent_at is None:
            await webhook_sender.send(payment)
            await mark_webhook_sent_use_case.execute(payment.id)

    except Exception as exc:
        logger.exception("Failed to deliver webhook")
        await retry_or_dead_letter(payload, headers, str(exc))
        return
