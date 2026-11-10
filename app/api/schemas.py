from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import AnyUrl, BaseModel, ConfigDict, Field

from app.domain.enums import Currency, PaymentStatus


class PaymentCreateRequest(BaseModel):
    amount: Decimal = Field(
        gt=0,
        max_digits=18,
        decimal_places=2,
    )

    currency: Currency

    description: str = Field(
        max_length=1024,
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )

    webhook_url: AnyUrl


class PaymentCreateResponse(BaseModel):
    payment_id: UUID
    status: PaymentStatus
    created_at: datetime


class PaymentReadResponse(BaseModel):
    id: UUID
    amount: Decimal
    currency: Currency
    description: str

    metadata: dict[str, Any] = Field(
        validation_alias="metadata_",
    )

    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    webhook_sent_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
