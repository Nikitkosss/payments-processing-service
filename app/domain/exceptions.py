from uuid import UUID


class PaymentNotFoundError(Exception):
    def __init__(self, payment_id: UUID):
        self.payment_id = payment_id
        super().__init__(f"Payment {payment_id} not found")


class WebhookDeliveryError(Exception):
    pass
