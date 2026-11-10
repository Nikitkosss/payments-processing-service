from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.core.config import get_settings

settings = get_settings()

broker = RabbitBroker(settings.rabbit_url)

payments_exchange = RabbitExchange(
    "payments",
    type=ExchangeType.TOPIC,
    durable=True,
)

new_queue = RabbitQueue(
    "payments.new",
    routing_key="payment.created",
    durable=True,
    arguments={
        "x-dead-letter-exchange": "payments",
        "x-dead-letter-routing-key": "payment.dead",
    },
)

dlq_queue = RabbitQueue(
    "payments.dlq",
    routing_key="payment.dead",
    durable=True,
)

retry_queues: list[RabbitQueue] = []

retry_delays_ms = (2000, 4000, 8000)

for attempt, ttl in enumerate(retry_delays_ms, start=1):
    retry_queues.append(
        RabbitQueue(
            f"payments.retry.{attempt}",
            routing_key=f"payment.retry.{attempt}",
            durable=True,
            arguments={
                "x-message-ttl": ttl,
                "x-dead-letter-exchange": "payments",
                "x-dead-letter-routing-key": "payment.created",
            },
        )
    )
