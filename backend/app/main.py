import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session
from .config import settings
from .db import SessionLocal, get_db, initialize_database
from .deps import current_user, role_required
from .checkout_service import (
    available_count,
    checkout_to_out,
    fulfill_checkout,
    release_checkout,
    release_expired_checkouts,
)
from .event_time import is_event_from_previous_day
from .models import CheckoutReservation, Event, PaymentCheckout, Reservation, Seat, Ticket, User
from .payments import StripePaymentGateway, get_payment_gateway
from .schemas import *
from .security import create_access_token, decode_ticket_token, hash_password, token_hash, verify_password
from .services import build_ticket, catalog_search, create_event_seats

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, list[WebSocket]] = {}
    async def connect(self, event_id: int, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(event_id, []).append(ws)
    def disconnect(self, event_id: int, ws: WebSocket):
        if event_id in self.connections and ws in self.connections[event_id]:
            self.connections[event_id].remove(ws)
    async def broadcast(self, event_id: int, payload: dict):
        stale = []
        for ws in self.connections.get(event_id, []):
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(event_id, ws)

manager = ConnectionManager()

def event_data(payload: EventCreate):
    data = payload.model_dump()
    data["image_url"] = str(payload.image_url) if payload.image_url else None
    return data

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/register", response_model=TokenOut)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(409, "Email already registered")
    user = User(name=payload.name, email=payload.email.lower(), password_hash=hash_password(payload.password), role=payload.role)
    db.add(user); db.commit(); db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id, user.role), user=user)

@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return TokenOut(access_token=create_access_token(user.id, user.role), user=user)

@app.get("/events", response_model=list[EventOut])
def list_events(q: str | None = Query(default=None), db: Session = Depends(get_db)):
    stmt = select(Event).where(Event.published.is_(True)).order_by(Event.starts_at)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Event.title.ilike(like), Event.location.ilike(like)))
    return list(db.scalars(stmt).all())

@app.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.scalar(
        select(Event).where(Event.id == event_id, Event.published.is_(True))
    )
    if not event:
        raise HTTPException(404, "Event not found")
    return event

@app.get("/events/{event_id}/seats", response_model=list[SeatOut])
def get_seats(event_id: int, db: Session = Depends(get_db)):
    event = db.scalar(
        select(Event).where(Event.id == event_id, Event.published.is_(True))
    )
    if not event:
        raise HTTPException(404, "Event not found")
    if event.event_type == "show":
        return []
    if release_expired_checkouts(db, event_id=event.id):
        db.commit()
    return list(db.scalars(select(Seat).where(Seat.event_id == event_id).order_by(Seat.row, Seat.number)).all())

@app.get("/events/{event_id}/availability", response_model=EventAvailabilityOut)
def get_event_availability(event_id: int, db: Session = Depends(get_db)):
    event = db.scalar(
        select(Event).where(Event.id == event_id, Event.published.is_(True))
    )
    if not event:
        raise HTTPException(404, "Event not found")
    if release_expired_checkouts(db, event_id=event.id):
        db.commit()
    available = available_count(db, event.id)
    return EventAvailabilityOut(capacity=event.capacity, available=available)

@app.post("/organizer/events", response_model=EventOut)
def create_event(payload: EventCreate, user: User = Depends(role_required("organizer")), db: Session = Depends(get_db)):
    event = Event(**event_data(payload), organizer_id=user.id)
    db.add(event); db.flush(); create_event_seats(db, event); db.commit(); db.refresh(event)
    return event

@app.get("/organizer/events", response_model=list[EventOut])
def organizer_events(user: User = Depends(role_required("organizer")), db: Session = Depends(get_db)):
    return list(db.scalars(select(Event).where(Event.organizer_id == user.id).order_by(Event.starts_at)).all())

@app.delete("/organizer/events/{event_id}")
def delete_event(event_id: int, user: User = Depends(role_required("organizer")), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Evento não encontrado.")
    if event.organizer_id != user.id:
        raise HTTPException(403, "Você só pode excluir seus próprios eventos.")

    starts_at = event.starts_at
    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    is_past_event = starts_at <= datetime.now(timezone.utc)

    if not is_past_event:
        active_reservation = db.scalar(
            select(Reservation.id)
            .where(
                Reservation.event_id == event.id,
                Reservation.status.in_(("pending", "confirmed")),
            )
            .limit(1)
        )
        if active_reservation:
            raise HTTPException(
                409,
                "Eventos futuros com reservas ativas não podem ser excluídos.",
            )

    checkout_ids = list(
        db.scalars(
            select(PaymentCheckout.id).where(PaymentCheckout.event_id == event.id)
        ).all()
    )
    if checkout_ids:
        db.execute(
            delete(CheckoutReservation).where(
                CheckoutReservation.checkout_id.in_(checkout_ids)
            )
        )
        db.execute(
            delete(PaymentCheckout).where(PaymentCheckout.id.in_(checkout_ids))
        )
    db.execute(delete(Ticket).where(Ticket.event_id == event.id))
    db.execute(delete(Reservation).where(Reservation.event_id == event.id))
    db.delete(event)
    db.commit()
    return {"message": "Evento excluído com sucesso."}

@app.get("/external/catalog")
def external_catalog(source: str = Query(pattern="^(tmdb|ticketmaster)$"), q: str = Query(min_length=1, max_length=200)):
    try:
        return catalog_search(source, q)
    except Exception as exc:
        raise HTTPException(502, f"External catalog error: {exc}") from exc

async def broadcast_inventory_changes(event_id: int, seats: list[Seat], db: Session):
    if not seats:
        return
    current_available = available_count(db, event_id)
    for seat in {seat.id: seat for seat in seats}.values():
        await manager.broadcast(
            event_id,
            {
                "type": "seat_updated",
                "seat_id": seat.id,
                "status": seat.status,
                "available_count": current_available,
            },
        )

def owned_checkout(db: Session, checkout_id: str, user_id: int, *, lock: bool = False):
    stmt = select(PaymentCheckout).where(
        PaymentCheckout.id == checkout_id,
        PaymentCheckout.user_id == user_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    checkout = db.scalar(stmt)
    if not checkout:
        raise HTTPException(404, "Checkout não encontrado.")
    return checkout

def stripe_object_value(value, key: str, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def stripe_public_error_message(exc: Exception) -> str:
    error_type = type(exc).__name__
    if error_type == "AuthenticationError":
        return "Não foi possível autenticar o pagamento. Entre em contato com o suporte."
    if error_type == "PermissionError":
        return "Não foi possível autorizar o pagamento. Entre em contato com o suporte."
    if error_type == "InvalidRequestError":
        return "Não foi possível preparar este pagamento. Tente novamente e, se o problema continuar, entre em contato com o suporte."
    if error_type == "RateLimitError":
        return "A Stripe recebeu muitas solicitações. Aguarde alguns segundos e tente novamente."
    if error_type in {"APIConnectionError", "APIError"}:
        return "Não foi possível comunicar com a Stripe agora. Tente novamente em instantes."
    return "Não foi possível iniciar o pagamento. Tente novamente e, se o problema continuar, entre em contato com o suporte."

def validate_paid_stripe_session(checkout: PaymentCheckout, stripe_session):
    amount_total = stripe_object_value(stripe_session, "amount_total")
    currency = stripe_object_value(stripe_session, "currency")
    metadata = stripe_object_value(stripe_session, "metadata", {}) or {}
    metadata_checkout_id = stripe_object_value(metadata, "checkout_id")
    if amount_total is None or int(amount_total) != checkout.amount_cents:
        raise HTTPException(409, "O valor confirmado pela Stripe não corresponde ao checkout.")
    if not currency or str(currency).lower() != checkout.currency:
        raise HTTPException(409, "A moeda confirmada pela Stripe não corresponde ao checkout.")
    if metadata_checkout_id != checkout.id:
        raise HTTPException(409, "A referência confirmada pela Stripe não corresponde ao checkout.")

@app.post("/checkout/sessions", response_model=CheckoutOut)
async def create_checkout_session(
    payload: CheckoutCreate,
    user: User = Depends(role_required("client")),
    db: Session = Depends(get_db),
    gateway: StripePaymentGateway = Depends(get_payment_gateway),
):
    event = db.scalar(
        select(Event).where(Event.id == payload.event_id).with_for_update()
    )
    if not event or not event.published:
        raise HTTPException(404, "Evento não encontrado.")
    if is_event_from_previous_day(event.starts_at):
        raise HTTPException(
            409,
            "Não é possível reservar ingressos para eventos de dias anteriores.",
        )
    if event.price_cents > 0 and not gateway.configured:
        raise HTTPException(
            503,
            "O pagamento com Stripe ainda não foi configurado pelo administrador.",
        )

    released_expired = release_expired_checkouts(db, event_id=event.id)
    if event.event_type == "show":
        if payload.seat_ids or payload.quantity is None:
            raise HTTPException(400, "Shows devem informar somente a quantidade de ingressos.")
        seats = list(
            db.scalars(
                select(Seat)
                .where(Seat.event_id == event.id, Seat.status == "available")
                .order_by(Seat.id)
                .limit(payload.quantity)
                .with_for_update(skip_locked=True)
            ).all()
        )
        if len(seats) != payload.quantity:
            raise HTTPException(409, "Não há ingressos suficientes disponíveis.")
    else:
        if payload.quantity is not None or not payload.seat_ids:
            raise HTTPException(400, "Filmes exigem a seleção de pelo menos um assento.")
        ordered_ids = sorted(payload.seat_ids)
        seats = list(
            db.scalars(
                select(Seat)
                .where(Seat.id.in_(ordered_ids), Seat.event_id == event.id)
                .order_by(Seat.id)
                .with_for_update()
            ).all()
        )
        if len(seats) != len(ordered_ids) or any(
            seat.status != "available" for seat in seats
        ):
            raise HTTPException(409, "Um ou mais assentos não estão mais disponíveis.")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=settings.stripe_checkout_expiration_minutes,
        seconds=15,
    )
    checkout = PaymentCheckout(
        id=str(uuid4()),
        user_id=user.id,
        event_id=event.id,
        provider="free" if event.price_cents == 0 else "stripe",
        status="pending",
        amount_cents=event.price_cents * len(seats),
        currency=settings.stripe_currency,
        expires_at=expires_at,
    )
    db.add(checkout)
    db.flush()

    for seat in seats:
        reservation = Reservation(
            event_id=event.id,
            seat_id=seat.id,
            user_id=user.id,
            status="pending",
            payment_status="pending",
        )
        db.add(reservation)
        seat.status = "reserved"
        db.flush()
        db.add(
            CheckoutReservation(
                checkout_id=checkout.id,
                reservation_id=reservation.id,
            )
        )
    db.flush()

    if event.price_cents == 0:
        fulfill_checkout(db, checkout, provider_payment_id=None)
    else:
        base_frontend_url = settings.frontend_url.rstrip("/")
        try:
            stripe_session = gateway.create_checkout_session(
                checkout_id=checkout.id,
                event_title=event.title,
                event_description=event.description or f"Ingresso para {event.title}",
                unit_amount=event.price_cents,
                quantity=len(seats),
                customer_email=user.email,
                success_url=(
                    f"{base_frontend_url}/checkout/{checkout.id}"
                    "?success=1&session_id={CHECKOUT_SESSION_ID}"
                ),
                cancel_url=f"{base_frontend_url}/checkout/{checkout.id}?cancelled=1",
                expires_at=int(expires_at.timestamp()),
                currency=checkout.currency,
            )
            if not stripe_session.url:
                raise RuntimeError("A Stripe não retornou uma URL de pagamento.")
            checkout.provider_session_id = stripe_session.id
            checkout.checkout_url = stripe_session.url
        except Exception as exc:
            logger.exception(
                "Falha ao criar Checkout Stripe (checkout_id=%s, event_id=%s, error_type=%s)",
                checkout.id,
                event.id,
                type(exc).__name__,
            )
            release_checkout(
                db,
                checkout,
                status="failed",
                payment_status="failed",
            )
            db.commit()
            raise HTTPException(
                502,
                stripe_public_error_message(exc),
            ) from exc

    db.commit()
    db.refresh(checkout)
    await broadcast_inventory_changes(event.id, released_expired + seats, db)
    return checkout_to_out(db, checkout)

@app.get("/checkout/sessions/{checkout_id}", response_model=CheckoutOut)
async def get_checkout_session(
    checkout_id: str,
    user: User = Depends(role_required("client")),
    db: Session = Depends(get_db),
):
    checkout = owned_checkout(db, checkout_id, user.id, lock=True)
    changed_seats = release_expired_checkouts(db, event_id=checkout.event_id)
    if changed_seats:
        db.commit()
        db.refresh(checkout)
        await broadcast_inventory_changes(checkout.event_id, changed_seats, db)
    return checkout_to_out(db, checkout)

@app.post("/checkout/sessions/{checkout_id}/sync", response_model=CheckoutOut)
async def sync_checkout_session(
    checkout_id: str,
    payload: CheckoutSyncIn,
    user: User = Depends(role_required("client")),
    db: Session = Depends(get_db),
    gateway: StripePaymentGateway = Depends(get_payment_gateway),
):
    checkout = owned_checkout(db, checkout_id, user.id, lock=True)
    if checkout.provider != "stripe" or checkout.provider_session_id != payload.session_id:
        raise HTTPException(400, "Sessão da Stripe inválida para este checkout.")
    if not gateway.configured:
        raise HTTPException(503, "A Stripe ainda não foi configurada.")

    try:
        stripe_session = gateway.retrieve_checkout_session(payload.session_id)
    except Exception as exc:
        logger.exception(
            "Falha ao consultar Checkout Stripe (checkout_id=%s, error_type=%s)",
            checkout.id,
            type(exc).__name__,
        )
        raise HTTPException(502, "Não foi possível confirmar o pagamento na Stripe.") from exc

    changed_seats: list[Seat] = []
    if stripe_session.payment_status == "paid":
        validate_paid_stripe_session(checkout, stripe_session)
        fulfill_checkout(
            db,
            checkout,
            provider_payment_id=stripe_session.payment_intent,
        )
    elif stripe_session.status == "expired":
        changed_seats = release_checkout(
            db,
            checkout,
            status="expired",
            payment_status="expired",
        )
    elif stripe_session.status == "complete":
        checkout.status = "processing"

    db.commit()
    db.refresh(checkout)
    await broadcast_inventory_changes(checkout.event_id, changed_seats, db)
    return checkout_to_out(db, checkout)

@app.post("/checkout/sessions/{checkout_id}/cancel", response_model=CheckoutOut)
async def cancel_checkout_session(
    checkout_id: str,
    user: User = Depends(role_required("client")),
    db: Session = Depends(get_db),
    gateway: StripePaymentGateway = Depends(get_payment_gateway),
):
    checkout = owned_checkout(db, checkout_id, user.id, lock=True)
    if checkout.status == "processing":
        raise HTTPException(409, "O pagamento está sendo processado e não pode ser cancelado agora.")
    if checkout.status != "pending":
        return checkout_to_out(db, checkout)

    if checkout.provider == "stripe" and checkout.provider_session_id:
        try:
            stripe_session = gateway.retrieve_checkout_session(
                checkout.provider_session_id
            )
            if stripe_session.payment_status == "paid":
                validate_paid_stripe_session(checkout, stripe_session)
                fulfill_checkout(
                    db,
                    checkout,
                    provider_payment_id=stripe_session.payment_intent,
                )
                db.commit()
                db.refresh(checkout)
                return checkout_to_out(db, checkout)
            if stripe_session.status == "complete":
                checkout.status = "processing"
                db.commit()
                db.refresh(checkout)
                return checkout_to_out(db, checkout)
            if stripe_session.status == "open":
                gateway.expire_checkout_session(checkout.provider_session_id)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Falha ao cancelar Checkout Stripe (checkout_id=%s, error_type=%s)",
                checkout.id,
                type(exc).__name__,
            )
            raise HTTPException(
                502,
                "Não foi possível cancelar a sessão na Stripe. Tente novamente.",
            ) from exc

    changed_seats = release_checkout(
        db,
        checkout,
        status="cancelled",
        payment_status="cancelled",
    )
    db.commit()
    db.refresh(checkout)
    await broadcast_inventory_changes(checkout.event_id, changed_seats, db)
    return checkout_to_out(db, checkout)

@app.post("/payments/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
    gateway: StripePaymentGateway = Depends(get_payment_gateway),
):
    if not stripe_signature:
        raise HTTPException(400, "Assinatura da Stripe ausente.")
    if not gateway.webhook_secret:
        raise HTTPException(503, "Webhook da Stripe ainda não foi configurado.")
    try:
        event_payload = gateway.construct_webhook_event(
            await request.body(),
            stripe_signature,
        )
    except Exception as exc:
        raise HTTPException(400, "Assinatura da Stripe inválida.") from exc

    event_type = stripe_object_value(event_payload, "type")
    event_data = stripe_object_value(event_payload, "data", {}) or {}
    stripe_session = stripe_object_value(event_data, "object", {}) or {}
    session_id = stripe_object_value(stripe_session, "id")
    if not session_id or not str(event_type).startswith("checkout.session."):
        return {"received": True}

    checkout = db.scalar(
        select(PaymentCheckout)
        .where(PaymentCheckout.provider_session_id == session_id)
        .with_for_update()
    )
    if not checkout:
        return {"received": True}

    changed_seats: list[Seat] = []
    payment_status = stripe_object_value(stripe_session, "payment_status")
    payment_intent = stripe_object_value(stripe_session, "payment_intent")
    if payment_intent is not None and not isinstance(payment_intent, str):
        payment_intent = stripe_object_value(payment_intent, "id")

    if event_type in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        if payment_status == "paid":
            validate_paid_stripe_session(checkout, stripe_session)
            fulfill_checkout(
                db,
                checkout,
                provider_payment_id=payment_intent,
            )
        elif checkout.status == "pending":
            checkout.status = "processing"
    elif event_type == "checkout.session.async_payment_failed":
        changed_seats = release_checkout(
            db,
            checkout,
            status="failed",
            payment_status="declined",
        )
    elif event_type == "checkout.session.expired":
        changed_seats = release_checkout(
            db,
            checkout,
            status="expired",
            payment_status="expired",
        )

    db.commit()
    await broadcast_inventory_changes(checkout.event_id, changed_seats, db)
    return {"received": True}

def reservation_to_out(reservation: Reservation, ticket_id: int | None = None):
    return ReservationOut(id=reservation.id, status=reservation.status, payment_status=reservation.payment_status, ticket_id=ticket_id)

@app.post("/reservations/{reservation_id}/cancel", response_model=ReservationOut)
async def cancel_reservation(reservation_id: int, user: User = Depends(role_required("client")), db: Session = Depends(get_db)):
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(404, "Reserva não encontrada.")
    ticket = db.scalar(select(Ticket).where(Ticket.reservation_id == reservation.id))
    if reservation.status != "confirmed" or not ticket or ticket.status != "valid":
        raise HTTPException(409, "Somente ingressos válidos podem ser cancelados.")
    checkout = db.scalar(
        select(PaymentCheckout)
        .join(
            CheckoutReservation,
            CheckoutReservation.checkout_id == PaymentCheckout.id,
        )
        .where(CheckoutReservation.reservation_id == reservation.id)
    )
    if checkout and checkout.provider == "stripe" and checkout.provider_payment_id:
        gateway = get_payment_gateway()
        if not gateway.configured:
            raise HTTPException(
                503,
                "A Stripe não está configurada para processar o reembolso.",
            )
        event = db.get(Event, reservation.event_id)
        try:
            gateway.create_refund(
                checkout.provider_payment_id,
                event.price_cents,
                ticket.id,
            )
        except Exception as exc:
            logger.exception(
                "Falha ao reembolsar ingresso na Stripe (ticket_id=%s, checkout_id=%s, error_type=%s)",
                ticket.id,
                checkout.id,
                type(exc).__name__,
            )
            raise HTTPException(
                502,
                "A Stripe não conseguiu processar o reembolso. O ingresso continua válido.",
            ) from exc
    reservation.status = "cancelled"; reservation.payment_status = "refunded"
    seat = db.get(Seat, reservation.seat_id); seat.status = "available"
    ticket.status = "cancelled"
    if checkout:
        remaining_confirmed = db.scalar(
            select(func.count(Reservation.id))
            .join(
                CheckoutReservation,
                CheckoutReservation.reservation_id == Reservation.id,
            )
            .where(
                CheckoutReservation.checkout_id == checkout.id,
                Reservation.id != reservation.id,
                Reservation.status == "confirmed",
            )
        ) or 0
        checkout.status = "partially_refunded" if remaining_confirmed else "refunded"
    db.commit()
    available_count = db.scalar(
        select(func.count(Seat.id)).where(
            Seat.event_id == reservation.event_id,
            Seat.status == "available",
        )
    ) or 0
    await manager.broadcast(
        reservation.event_id,
        {
            "type": "seat_updated",
            "seat_id": seat.id,
            "status": seat.status,
            "available_count": available_count,
        },
    )
    return reservation_to_out(reservation, ticket.id)

@app.post("/tickets/{ticket_id}/cancel", response_model=ReservationOut)
async def cancel_ticket(ticket_id: int, user: User = Depends(role_required("client")), db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.user_id != user.id:
        raise HTTPException(404, "Ingresso não encontrado.")
    return await cancel_reservation(ticket.reservation_id, user, db)

@app.get("/tickets", response_model=list[TicketOut])
def my_tickets(user: User = Depends(role_required("client")), db: Session = Depends(get_db)):
    stmt = select(Ticket, Event.title, Event.event_type, Seat.label).join(Event, Event.id == Ticket.event_id).join(Reservation, Reservation.id == Ticket.reservation_id).join(Seat, Seat.id == Reservation.seat_id).where(Ticket.user_id == user.id).order_by(Ticket.id.desc())
    rows = db.execute(stmt).all()
    out = []
    repaired_legacy_hash = False
    from .config import settings
    from .security import create_ticket_token
    for ticket, title, event_type, seat_label in rows:
        token = create_ticket_token(
            ticket.id,
            ticket.event_id,
            ticket.code_jti,
            ticket.created_at,
        )
        stable_token_hash = token_hash(token)
        if ticket.token_hash != stable_token_hash:
            ticket.token_hash = stable_token_hash
            repaired_legacy_hash = True
        out.append(TicketOut(id=ticket.id, event_id=ticket.event_id, event_title=title, event_type=event_type, seat_label=None if event_type == "show" else seat_label, token=token, status=ticket.status, share_url=f"{settings.frontend_url}/share/{token}", used_at=ticket.used_at))
    if repaired_legacy_hash:
        db.commit()
    return out

@app.get("/share/{token}", response_model=TicketOut)
def share_ticket(token: str, db: Session = Depends(get_db)):
    try:
        payload = decode_ticket_token(token)
    except Exception:
        raise HTTPException(400, "Invalid ticket")
    ticket = db.get(Ticket, int(payload["ticket_id"]))
    if not ticket or ticket.code_jti != payload["jti"] or token_hash(token) != ticket.token_hash:
        raise HTTPException(404, "Ticket not found")
    event = db.get(Event, ticket.event_id)
    reservation = db.get(Reservation, ticket.reservation_id)
    seat = db.get(Seat, reservation.seat_id)
    from .config import settings
    return TicketOut(id=ticket.id, event_id=ticket.event_id, event_title=event.title, event_type=event.event_type, seat_label=None if event.event_type == "show" else seat.label, token=token, status=ticket.status, share_url=f"{settings.frontend_url}/share/{token}", used_at=ticket.used_at)

@app.post("/gate/validate", response_model=GateValidationOut)
def validate_ticket(payload: GateValidationIn, user: User = Depends(role_required("gate")), db: Session = Depends(get_db)):
    try:
        decoded = decode_ticket_token(payload.code)
    except Exception:
        return GateValidationOut(result="invalid", message="Código inválido ou adulterado")
    ticket = db.scalar(
        select(Ticket)
        .where(Ticket.id == int(decoded.get("ticket_id", 0)))
        .with_for_update()
    )
    if not ticket or ticket.code_jti != decoded.get("jti") or token_hash(payload.code) != ticket.token_hash:
        return GateValidationOut(result="invalid", message="Ingresso não encontrado")
    if ticket.event_id != payload.event_id:
        return GateValidationOut(result="event_wrong", message="Ingresso pertence a outro evento", ticket_id=ticket.id)
    event = db.get(Event, ticket.event_id)
    if not event:
        return GateValidationOut(result="invalid", message="Evento não encontrado", ticket_id=ticket.id)
    if is_event_from_previous_day(event.starts_at):
        return GateValidationOut(
            result="invalid",
            message="Não é possível validar ingressos de eventos de dias anteriores",
            ticket_id=ticket.id,
        )
    if ticket.status == "used":
        return GateValidationOut(result="already_used", message="Ingresso já utilizado", ticket_id=ticket.id)
    if ticket.status != "valid":
        return GateValidationOut(result="invalid", message="Ingresso não está válido", ticket_id=ticket.id)
    ticket.status = "used"; ticket.used_at = datetime.now(timezone.utc)
    db.commit()
    return GateValidationOut(result="valid", message="Entrada autorizada", ticket_id=ticket.id)

@app.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

@app.websocket("/ws/events/{event_id}/seats")
async def seat_socket(websocket: WebSocket, event_id: int):
    with SessionLocal() as db:
        published_event = db.scalar(
            select(Event.id).where(
                Event.id == event_id,
                Event.published.is_(True),
            )
        )
    if published_event is None:
        await websocket.close(code=1008, reason="Evento não encontrado")
        return

    await manager.connect(event_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(event_id, websocket)
