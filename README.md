# Payments Processing Service

Асинхронный микросервис процессинга платежей.

Сервис принимает запрос на создание платежа, публикует событие через `Outbox pattern`, обрабатывает его через consumer и уведомляет клиента через webhook.

## Стек

- FastAPI
- Pydantic v2
- SQLAlchemy 2.1 async
- PostgreSQL
- RabbitMQ
- FastStream
- Alembic
- Docker / Docker Compose

## Архитектура

```text
Client
  │
  ▼
API (FastAPI)
  │  1. проверка X-API-Key
  │  2. проверка Idempotency-Key
  │  3. INSERT payment + INSERT outbox event
  │
  ▼
PostgreSQL
  │
  ▼
Outbox relay
  │  читает unpublished events
  │  публикует в RabbitMQ
  ▼
RabbitMQ queue: payments.new
  │
  ▼
Consumer
  │  1. симулирует обработку 2–5 сек
  │  2. 90% succeeded / 10% failed
  │  3. обновляет payment.status
  │  4. отправляет webhook
  ▼
Client webhook URL
```

## Гарантии и паттерны

### Outbox pattern

При создании платежа запись в `payments` и запись в `outbox` происходят в одной транзакции.

Это гарантирует:

- платёж не будет создан без события;
- событие не потеряется, если RabbitMQ временно недоступен.

`OutboxRelay` периодически выбирает неопубликованные события и публикует их в очередь `payments.new`.

Доставка из RabbitMQ — at-least-once. Между успешной публикацией и записью `published_at` процесс может упасть, и событие уйдёт в брокер ещё раз. Consumer это переживает: статус меняется только из `pending`, webhook уходит только пока `webhook_sent_at` пустой.

Webhook вызывается по HTTP уже после коммита статуса. Соединение с клиентом не держится внутри транзакции базы.

### Idempotency

Используется заголовок:

```text
Idempotency-Key
```

В БД поле `idempotency_key` уникально.

Повторный запрос с тем же `Idempotency-Key` вернёт уже существующий платёж.

### Идемпотентный consumer

Потребитель обрабатывает сообщения идемпотентно:

- статус платежа обновляется только если платёж находится в статусе `pending`;
- webhook отправляется только если `webhook_sent_at IS NULL`.

### Retry

При ошибках обработки или доставки вебхука сообщение уходит в retry-очередь. Заголовок `x-attempts` считает уже сделанные неудачи.

```text
payments.new
  fail (x-attempts=0)
payments.retry.1  TTL 2s
  expired
payments.new
  fail (x-attempts=1)
payments.retry.2  TTL 4s
  expired
payments.new
  fail (x-attempts=2)
payments.retry.3  TTL 8s
  expired
payments.new
  fail (x-attempts=3)
payments.dlq
```

Это первая обработка и три повтора. На четвёртой неудаче сообщение публикуется в `payments.dlq`. `MAX_DELIVERY_ATTEMPTS=3` — это число retry-очередей, а не общее число обработок.

## Запуск

```bash
docker compose up --build
```

API-контейнер сам применяет миграции Alembic. Ключ в Compose — `test-api-key`, его и нужно передавать в `X-API-Key`. Значение `change-me` из `.env.example` относится к запуску без Compose.

API:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

RabbitMQ management UI:

```text
http://localhost:15672
```

Логин/пароль по умолчанию:

```text
guest/guest
```

## Переменные окружения

```dotenv
API_KEY=change-me
DATABASE_URL=postgresql+asyncpg://payments:payments@localhost:5432/payments
RABBIT_URL=amqp://guest:guest@localhost:5672//
OUTBOX_POLL_INTERVAL=1.0
OUTBOX_BATCH_SIZE=100
WEBHOOK_TIMEOUT=10.0
MAX_DELIVERY_ATTEMPTS=3
LOG_LEVEL=INFO
LOG_JSON=false
```

## Создание платежа

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: test-api-key" \
  -H "Idempotency-Key: 123e4567-e89b-12d3-a456-426614174000" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "100.50",
    "currency": "RUB",
    "description": "Test payment",
    "metadata": {
      "order_id": "order-1"
    },
    "webhook_url": "https://webhook.site/your-url"
  }'
```

Пример ответа:

```json
{
  "payment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending",
  "created_at": "2026-11-09T12:00:00Z"
}
```

## Получение платежа

```bash
curl http://localhost:8000/api/v1/payments/3fa85f64-5717-4562-b3fc-2c963f66afa6 \
  -H "X-API-Key: test-api-key"
```

В ответе идентификатор лежит в поле `id`, не `payment_id`:

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "amount": "100.50",
  "currency": "RUB",
  "description": "Test payment",
  "metadata": {
    "order_id": "order-1"
  },
  "status": "pending",
  "idempotency_key": "123e4567-e89b-12d3-a456-426614174000",
  "webhook_url": "https://webhook.site/your-url",
  "created_at": "2026-11-09T12:00:00Z",
  "updated_at": "2026-11-09T12:00:00Z",
  "processed_at": null,
  "webhook_sent_at": null
}
```

## Тесты

Установить зависимости:

```bash
pip install -r requirements-dev.txt
```

Запустить тесты:

```bash
pytest
```

Тесты используют SQLite через `aiosqlite`, поэтому для них не нужно поднимать PostgreSQL и RabbitMQ.

## Логирование

Сервис поддерживает обычный текстовый и JSON-формат логов.

Переменные:

```dotenv
LOG_LEVEL=INFO
LOG_JSON=false
```

Если включить:

```dotenv
LOG_JSON=true
```

логи будут выводиться в структурированном JSON-формате.

HTTP API пишет `trace_id` из заголовка:

```text
X-Request-ID
```

Если заголовок не передан, сервис сгенерирует его сам.
