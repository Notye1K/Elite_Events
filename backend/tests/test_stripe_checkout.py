import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.deps import current_user
from app.main import app, stripe_public_error_message
from app.models import Event, PaymentCheckout, Reservation, Seat, Ticket, User
from app.payments import StripeCheckoutSession, StripePaymentGateway, get_payment_gateway


class FakeStripeGateway:
    def __init__(self):
        self.configured = True
        self.webhook_secret = "whsec_test"
        self.sessions: dict[str, StripeCheckoutSession] = {}
        self.expired_sessions: list[str] = []
        self.refunds: list[tuple[str, int, int]] = []

    def create_checkout_session(self, **kwargs):
        session_id = f"cs_test_{kwargs['checkout_id']}"
        session = StripeCheckoutSession(
            id=session_id,
            url=f"https://checkout.stripe.test/{session_id}",
            payment_status="unpaid",
            status="open",
            amount_total=kwargs["unit_amount"] * kwargs["quantity"],
            currency=kwargs["currency"],
            metadata={"checkout_id": kwargs["checkout_id"]},
        )
        self.sessions[session_id] = session
        return session

    def retrieve_checkout_session(self, session_id):
        return self.sessions[session_id]

    def expire_checkout_session(self, session_id):
        current = self.sessions[session_id]
        expired = StripeCheckoutSession(
            id=current.id,
            url=current.url,
            payment_status="unpaid",
            status="expired",
            amount_total=current.amount_total,
            currency=current.currency,
            metadata=current.metadata,
        )
        self.sessions[session_id] = expired
        self.expired_sessions.append(session_id)
        return expired

    def construct_webhook_event(self, payload, signature):
        assert signature == "test-signature"
        return json.loads(payload)

    def create_refund(self, payment_intent_id, amount_cents, ticket_id):
        self.refunds.append((payment_intent_id, amount_cents, ticket_id))
        return {"id": f"re_test_{ticket_id}"}


def test_gateway_blocks_live_key_while_test_mode_is_enabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "stripe_test_mode", True)

    assert StripePaymentGateway(secret_key="sk_test_example").configured is True
    assert StripePaymentGateway(secret_key="rk_test_example").configured is True
    assert StripePaymentGateway(secret_key="sk_live_example").configured is False


@pytest.mark.parametrize(
    ("error_type", "expected_message"),
    [
        (
            "AuthenticationError",
            "Não foi possível autenticar o pagamento. Entre em contato com o suporte.",
        ),
        (
            "PermissionError",
            "Não foi possível autorizar o pagamento. Entre em contato com o suporte.",
        ),
        (
            "InvalidRequestError",
            "Não foi possível preparar este pagamento. Tente novamente e, se o problema continuar, entre em contato com o suporte.",
        ),
        (
            "APIConnectionError",
            "Não foi possível comunicar com a Stripe agora. Tente novamente em instantes.",
        ),
    ],
)
def test_stripe_errors_have_safe_public_messages(error_type, expected_message):
    stripe_error = type(error_type, (Exception,), {})

    assert stripe_public_error_message(stripe_error()) == expected_message


def test_stripe_session_metadata_object_is_converted_without_key_error():
    class StripeMetadataObject:
        def to_dict(self):
            return {"checkout_id": "checkout-123"}

        def __getitem__(self, key):
            raise KeyError(key)

    session = SimpleNamespace(
        id="cs_test_123",
        url="https://checkout.stripe.test/cs_test_123",
        payment_status="unpaid",
        status="open",
        payment_intent=None,
        amount_total=5000,
        currency="brl",
        metadata=StripeMetadataObject(),
    )

    result = StripePaymentGateway._session_data(session)

    assert result.metadata == {"checkout_id": "checkout-123"}


@pytest.fixture
def checkout_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    gateway = FakeStripeGateway()

    with Session(engine, autoflush=False) as db:
        organizer = User(
            name="Organizador",
            email="organizer-checkout@teste.dev",
            password_hash="test",
            role="organizer",
        )
        client = User(
            name="Cliente",
            email="client-checkout@teste.dev",
            password_hash="test",
            role="client",
        )
        another_client = User(
            name="Outro cliente",
            email="another-checkout@teste.dev",
            password_hash="test",
            role="client",
        )
        db.add_all([organizer, client, another_client])
        db.flush()
        event = Event(
            title="Filme com Stripe",
            description="Checkout de teste",
            event_type="movie",
            starts_at=datetime.now(timezone.utc) + timedelta(days=2),
            location="Sala 1",
            capacity=2,
            price_cents=1500,
            published=True,
            organizer_id=organizer.id,
        )
        db.add(event)
        db.flush()
        seats = [
            Seat(
                event_id=event.id,
                label=f"A{number}",
                row="A",
                number=number,
                status="available",
            )
            for number in (1, 2)
        ]
        db.add_all(seats)
        db.commit()

        def override_db():
            yield db

        def override_user():
            return client

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[current_user] = override_user
        app.dependency_overrides[get_payment_gateway] = lambda: gateway
        api_client = TestClient(app)
        try:
            yield api_client, db, gateway, client, another_client, event, seats
        finally:
            api_client.close()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=engine)


def create_checkout(api_client, event, seats):
    response = api_client.post(
        "/checkout/sessions",
        json={"event_id": event.id, "seat_ids": [seat.id for seat in seats]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def checkout_event(event_type, checkout, *, payment_status="unpaid"):
    def value(name):
        return checkout[name] if isinstance(checkout, dict) else getattr(checkout, name)

    return {
        "type": event_type,
        "data": {
            "object": {
                "id": value("provider_session_id"),
                "payment_status": payment_status,
                "payment_intent": "pi_test_paid" if payment_status == "paid" else None,
                "amount_total": value("amount_cents"),
                "currency": value("currency"),
                "metadata": {"checkout_id": value("id")},
            }
        },
    }


def post_webhook(api_client, payload):
    return api_client.post(
        "/payments/stripe/webhook",
        content=json.dumps(payload),
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "test-signature",
        },
    )


def test_checkout_holds_inventory_until_stripe_confirms(checkout_context):
    api_client, db, _, _, _, event, seats = checkout_context

    result = create_checkout(api_client, event, seats)

    assert result["status"] == "pending"
    assert result["amount_cents"] == 3000
    assert result["checkout_url"].startswith("https://checkout.stripe.test/")
    assert all(db.get(Seat, seat.id).status == "reserved" for seat in seats)
    assert all(
        reservation.status == "pending"
        for reservation in db.scalars(select(Reservation)).all()
    )
    assert list(db.scalars(select(Ticket)).all()) == []


def test_second_checkout_cannot_hold_an_already_reserved_seat(checkout_context):
    api_client, db, _, _, another_client, event, seats = checkout_context
    create_checkout(api_client, event, seats[:1])
    app.dependency_overrides[current_user] = lambda: another_client

    response = api_client.post(
        "/checkout/sessions",
        json={"event_id": event.id, "seat_ids": [seats[0].id]},
    )

    assert response.status_code == 409
    assert "não estão mais disponíveis" in response.json()["detail"]
    assert db.get(Seat, seats[0].id).status == "reserved"


def test_paid_webhook_creates_tickets_once_even_when_repeated(checkout_context):
    api_client, db, _, _, _, event, seats = checkout_context
    result = create_checkout(api_client, event, seats)
    checkout = db.get(PaymentCheckout, result["id"])
    payload = checkout_event(
        "checkout.session.completed",
        checkout,
        payment_status="paid",
    )

    first = post_webhook(api_client, payload)
    second = post_webhook(api_client, payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert checkout.status == "paid"
    assert checkout.provider_payment_id == "pi_test_paid"
    assert len(list(db.scalars(select(Ticket)).all())) == 2
    assert all(
        reservation.status == "confirmed"
        and reservation.payment_status == "paid"
        for reservation in db.scalars(select(Reservation)).all()
    )


def test_failed_async_payment_releases_inventory_without_ticket(checkout_context):
    api_client, db, _, _, _, event, seats = checkout_context
    result = create_checkout(api_client, event, seats[:1])
    checkout = db.get(PaymentCheckout, result["id"])

    response = post_webhook(
        api_client,
        checkout_event("checkout.session.async_payment_failed", checkout),
    )

    assert response.status_code == 200
    assert checkout.status == "failed"
    assert db.get(Seat, seats[0].id).status == "available"
    assert db.scalar(select(Reservation)).status == "cancelled"
    assert list(db.scalars(select(Ticket)).all()) == []


def test_expired_checkout_webhook_releases_inventory(checkout_context):
    api_client, db, _, _, _, event, seats = checkout_context
    result = create_checkout(api_client, event, seats[:1])
    checkout = db.get(PaymentCheckout, result["id"])

    response = post_webhook(
        api_client,
        checkout_event("checkout.session.expired", checkout),
    )

    assert response.status_code == 200
    assert checkout.status == "expired"
    assert db.get(Seat, seats[0].id).status == "available"


def test_return_sync_confirms_paid_session_without_waiting_for_webhook(checkout_context):
    api_client, db, gateway, _, _, event, seats = checkout_context
    result = create_checkout(api_client, event, seats[:1])
    checkout = db.get(PaymentCheckout, result["id"])
    current = gateway.sessions[checkout.provider_session_id]
    gateway.sessions[checkout.provider_session_id] = StripeCheckoutSession(
        id=current.id,
        url=current.url,
        payment_status="paid",
        status="complete",
        payment_intent="pi_test_sync",
        amount_total=checkout.amount_cents,
        currency=checkout.currency,
        metadata={"checkout_id": checkout.id},
    )

    response = api_client.post(
        f"/checkout/sessions/{checkout.id}/sync",
        json={"session_id": checkout.provider_session_id},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "paid"
    assert len(list(db.scalars(select(Ticket)).all())) == 1


def test_client_can_cancel_open_checkout_and_release_inventory(checkout_context):
    api_client, db, gateway, _, _, event, seats = checkout_context
    result = create_checkout(api_client, event, seats[:1])
    checkout = db.get(PaymentCheckout, result["id"])

    response = api_client.post(f"/checkout/sessions/{checkout.id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert checkout.provider_session_id in gateway.expired_sessions
    assert db.get(Seat, seats[0].id).status == "available"


def test_cancelling_paid_ticket_refunds_stripe_and_releases_inventory(
    checkout_context,
    monkeypatch,
):
    api_client, db, gateway, _, _, event, seats = checkout_context
    result = create_checkout(api_client, event, seats[:1])
    checkout = db.get(PaymentCheckout, result["id"])
    paid = post_webhook(
        api_client,
        checkout_event("checkout.session.completed", checkout, payment_status="paid"),
    )
    assert paid.status_code == 200
    ticket = db.scalar(select(Ticket))
    monkeypatch.setattr("app.main.get_payment_gateway", lambda: gateway)

    response = api_client.post(f"/tickets/{ticket.id}/cancel")

    assert response.status_code == 200
    assert gateway.refunds == [("pi_test_paid", event.price_cents, ticket.id)]
    assert checkout.status == "refunded"
    assert ticket.status == "cancelled"
    assert db.get(Seat, seats[0].id).status == "available"


def test_client_cannot_read_another_clients_checkout(checkout_context):
    api_client, _, _, _, another_client, event, seats = checkout_context
    result = create_checkout(api_client, event, seats[:1])
    app.dependency_overrides[current_user] = lambda: another_client

    response = api_client.get(f"/checkout/sessions/{result['id']}")

    assert response.status_code == 404


def test_non_client_role_cannot_create_checkout(checkout_context):
    api_client, db, _, _, _, event, seats = checkout_context
    organizer = db.scalar(select(User).where(User.role == "organizer"))
    app.dependency_overrides[current_user] = lambda: organizer

    response = api_client.post(
        "/checkout/sessions",
        json={"event_id": event.id, "seat_ids": [seats[0].id]},
    )

    assert response.status_code == 403
    assert db.get(Seat, seats[0].id).status == "available"


def test_free_event_creates_ticket_without_stripe_session(checkout_context):
    api_client, db, gateway, _, _, event, seats = checkout_context
    event.price_cents = 0
    db.commit()

    result = create_checkout(api_client, event, seats[:1])

    assert result["status"] == "paid"
    assert result["checkout_url"] is None
    assert result["amount_cents"] == 0
    assert gateway.sessions == {}
    assert len(list(db.scalars(select(Ticket)).all())) == 1
