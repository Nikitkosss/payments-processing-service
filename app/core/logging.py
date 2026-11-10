import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

_RESERVED_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "trace_id",
}


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_ATTRS:
                continue

            if key.startswith("_"):
                continue

            if key in payload:
                continue

            payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)

    if json_logs:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | trace_id=%(trace_id)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )

    handler.setFormatter(formatter)
    handler.addFilter(ContextFilter())

    root_logger.handlers = [handler]

    for logger_name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "faststream",
        "aio_pika",
        "aiormq",
        "sqlalchemy.engine",
    ):
        logger = logging.getLogger(logger_name)
        logger.handlers = [handler]
        logger.propagate = False
