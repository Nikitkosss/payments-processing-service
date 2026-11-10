import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.dependencies import (
    get_create_payment_use_case,
    get_get_payment_use_case,
    require_api_key,
)
from app.api.schemas import (
    PaymentCreateRequest,
    PaymentCreateResponse,
    PaymentReadResponse,
)
from app.services.create_payment import CreatePaymentCommand, CreatePaymentUseCase
from app.services.get_payment import GetPaymentUseCase

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/payments",
    tags=["payments"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PaymentCreateResponse,
)
async def create_payment(
    payload: PaymentCreateRequest,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=16,
            max_length=128,
        ),
    ],
    use_case: Annotated[
        CreatePaymentUseCase,
        Depends(get_create_payment_use_case),
    ],
):
    command = CreatePaymentCommand(
        idempotency_key=idempotency_key,
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
        metadata=payload.metadata,
        webhook_url=str(payload.webhook_url),
    )

    payment = await use_case.execute(command)

    return PaymentCreateResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentReadResponse,
    response_model_by_alias=True,
)
async def get_payment(
    payment_id: UUID,
    use_case: Annotated[
        GetPaymentUseCase,
        Depends(get_get_payment_use_case),
    ],
):
    payment = await use_case.execute(payment_id)

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return PaymentReadResponse.model_validate(payment)
