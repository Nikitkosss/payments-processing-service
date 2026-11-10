import hmac
from typing import Annotated, Callable

from fastapi import Depends, Header, HTTPException, status

from app.core.config import get_settings
from app.db.session import session_factory
from app.infrastructure.uow import AbstractUnitOfWork, SqlAlchemyUnitOfWork
from app.services.create_payment import CreatePaymentUseCase
from app.services.get_payment import GetPaymentUseCase

settings = get_settings()


async def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    if not hmac.compare_digest(
        x_api_key.encode("utf-8"),
        settings.api_key.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


def get_uow_factory() -> Callable[[], AbstractUnitOfWork]:
    return lambda: SqlAlchemyUnitOfWork(session_factory)


def get_create_payment_use_case(
    uow_factory: Annotated[
        Callable[[], AbstractUnitOfWork],
        Depends(get_uow_factory),
    ],
) -> CreatePaymentUseCase:
    return CreatePaymentUseCase(uow_factory)


def get_get_payment_use_case(
    uow_factory: Annotated[
        Callable[[], AbstractUnitOfWork],
        Depends(get_uow_factory),
    ],
) -> GetPaymentUseCase:
    return GetPaymentUseCase(uow_factory)
