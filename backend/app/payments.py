from dataclasses import dataclass
from typing import Any

import stripe

from .config import settings


@dataclass(frozen=True)
class StripeCheckoutSession:
    id: str
    url: str
    payment_status: str
    status: str
    payment_intent: str | None = None
    amount_total: int | None = None
    currency: str | None = None
    metadata: dict[str, str] | None = None


class StripePaymentGateway:
    def __init__(self, secret_key: str | None = None, webhook_secret: str | None = None):
        self.secret_key = secret_key or settings.stripe_secret_key
        self.webhook_secret = webhook_secret or settings.stripe_webhook_secret
        self._client = stripe.StripeClient(self.secret_key) if self.secret_key else None

    @property
    def configured(self) -> bool:
        if self._client is None or not self.secret_key:
            return False
        if settings.stripe_test_mode:
            return self.secret_key.startswith(("sk_test_", "rk_test_"))
        return True

    def create_checkout_session(
        self,
        *,
        checkout_id: str,
        event_title: str,
        event_description: str,
        unit_amount: int,
        quantity: int,
        customer_email: str,
        success_url: str,
        cancel_url: str,
        expires_at: int,
        currency: str,
    ) -> StripeCheckoutSession:
        if not self.configured:
            raise RuntimeError("Stripe não está configurada.")

        session = self._client.v1.checkout.sessions.create(
            {
                "mode": "payment",
                "client_reference_id": checkout_id,
                "customer_email": customer_email,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "expires_at": expires_at,
                "locale": "pt-BR",
                "metadata": {"checkout_id": checkout_id},
                "payment_intent_data": {"metadata": {"checkout_id": checkout_id}},
                "line_items": [
                    {
                        "quantity": quantity,
                        "price_data": {
                            "currency": currency,
                            "unit_amount": unit_amount,
                            "product_data": {
                                "name": event_title,
                                "description": event_description[:500],
                            },
                        },
                    }
                ],
            },
            options={"idempotency_key": f"elite-checkout-{checkout_id}"},
        )
        return self._session_data(session)

    def retrieve_checkout_session(self, session_id: str) -> StripeCheckoutSession:
        if not self.configured:
            raise RuntimeError("Stripe não está configurada.")
        return self._session_data(self._client.v1.checkout.sessions.retrieve(session_id))

    def expire_checkout_session(self, session_id: str) -> StripeCheckoutSession:
        if not self.configured:
            raise RuntimeError("Stripe não está configurada.")
        return self._session_data(self._client.v1.checkout.sessions.expire(session_id))

    def create_refund(self, payment_intent_id: str, amount_cents: int, ticket_id: int):
        if not self.configured:
            raise RuntimeError("Stripe não está configurada.")
        return self._client.v1.refunds.create(
            {"payment_intent": payment_intent_id, "amount": amount_cents},
            options={"idempotency_key": f"elite-ticket-refund-{ticket_id}"},
        )

    def construct_webhook_event(self, payload: bytes, signature: str) -> dict[str, Any]:
        if not self.webhook_secret:
            raise RuntimeError("Webhook da Stripe não está configurado.")
        return stripe.Webhook.construct_event(payload, signature, self.webhook_secret)

    @staticmethod
    def _session_data(session: Any) -> StripeCheckoutSession:
        payment_intent = getattr(session, "payment_intent", None)
        if payment_intent is not None and not isinstance(payment_intent, str):
            payment_intent = getattr(payment_intent, "id", None)
        metadata = getattr(session, "metadata", None)
        to_dict = getattr(metadata, "to_dict", None)
        if callable(to_dict):
            metadata = to_dict()
        if not isinstance(metadata, dict):
            metadata = {}
        return StripeCheckoutSession(
            id=session.id,
            url=session.url or "",
            payment_status=session.payment_status or "unpaid",
            status=session.status or "open",
            payment_intent=payment_intent,
            amount_total=getattr(session, "amount_total", None),
            currency=getattr(session, "currency", None),
            metadata={str(key): str(value) for key, value in metadata.items()},
        )


def get_payment_gateway() -> StripePaymentGateway:
    return StripePaymentGateway()
