import asyncio

from faststream import FastStream

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.messaging.broker import broker
from app.messaging.consumer import handle_payment_created  # noqa: F401
from app.messaging.topology import declare_rabbit_topology

settings = get_settings()

setup_logging(
    level=settings.log_level,
    json_logs=settings.log_json,
)

app = FastStream(broker)


async def main() -> None:
    await declare_rabbit_topology()
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
