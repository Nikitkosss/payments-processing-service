import aio_pika

from app.core.config import get_settings

settings = get_settings()


async def declare_rabbit_topology() -> None:
    """
    Гарантированно объявляем обменник, очереди и DLQ.

    Это особенно важно для API/relay, потому что API публикует
    сообщения, но не является потребителем этих очередей.
    """
    connection = await aio_pika.connect_robust(settings.rabbit_url)

    async with connection:
        channel = await connection.channel()

        exchange = await channel.declare_exchange(
            "payments",
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        new_queue = await channel.declare_queue(
            "payments.new",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "payments",
                "x-dead-letter-routing-key": "payment.dead",
            },
        )
        await new_queue.bind(exchange, routing_key="payment.created")

        retry_delays_ms = (2000, 4000, 8000)

        for attempt, ttl in enumerate(retry_delays_ms, start=1):
            retry_queue = await channel.declare_queue(
                f"payments.retry.{attempt}",
                durable=True,
                arguments={
                    "x-message-ttl": ttl,
                    "x-dead-letter-exchange": "payments",
                    "x-dead-letter-routing-key": "payment.created",
                },
            )
            await retry_queue.bind(exchange, routing_key=f"payment.retry.{attempt}")

        dlq_queue = await channel.declare_queue(
            "payments.dlq",
            durable=True,
        )
        await dlq_queue.bind(exchange, routing_key="payment.dead")
