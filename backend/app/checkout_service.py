from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    CheckoutReservation,
    Event,
    PaymentCheckout,
    Reservation,
    Seat,
    Ticket,
)
from .schemas import CheckoutOut
from .services import build_ticket


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def reservations_for_checkout(db: Session, checkout_id: str) -> list[Reservation]:
    return list(
        db.scalars(
            select(Reservation)
            .join(
                CheckoutReservation,
                CheckoutReservation.reservation_id == Reservation.id,
            )
            .where(CheckoutReservation.checkout_id == checkout_id)
            .order_by(Reservation.id)
        ).all()
    )


def release_checkout(
    db: Session,
    checkout: PaymentCheckout,
    *,
    status: str,
    payment_status: str,
) -> list[Seat]:
    if checkout.status not in {"pending", "processing"}:
        return []

    changed_seats: list[Seat] = []
    for reservation in reservations_for_checkout(db, checkout.id):
        if reservation.status != "pending":
            continue
        reservation.status = "cancelled"
        reservation.payment_status = payment_status
        seat = db.get(Seat, reservation.seat_id)
        if seat and seat.status == "reserved":
            seat.status = "available"
            changed_seats.append(seat)

    checkout.status = status
    return changed_seats


def release_expired_checkouts(
    db: Session,
    *,
    event_id: int | None = None,
    now: datetime | None = None,
) -> list[Seat]:
    reference = aware_utc(now or datetime.now(timezone.utc))
    stmt = select(PaymentCheckout).where(
        PaymentCheckout.status == "pending",
        PaymentCheckout.provider != "stripe",
    )
    if event_id is not None:
        stmt = stmt.where(PaymentCheckout.event_id == event_id)

    changed_seats: list[Seat] = []
    for checkout in db.scalars(stmt.with_for_update()).all():
        if aware_utc(checkout.expires_at) <= reference:
            changed_seats.extend(
                release_checkout(
                    db,
                    checkout,
                    status="expired",
                    payment_status="expired",
                )
            )
    return changed_seats


def fulfill_checkout(
    db: Session,
    checkout: PaymentCheckout,
    *,
    provider_payment_id: str | None,
) -> list[Ticket]:
    if checkout.status == "paid":
        return tickets_for_checkout(db, checkout.id)
    if checkout.status not in {"pending", "processing"}:
        raise ValueError("Checkout não pode mais ser confirmado.")

    event = db.get(Event, checkout.event_id)
    if not event:
        raise ValueError("Evento do checkout não foi encontrado.")

    tickets: list[Ticket] = []
    for reservation in reservations_for_checkout(db, checkout.id):
        if reservation.status != "pending":
            raise ValueError("Reserva do checkout não está pendente.")
        reservation.status = "confirmed"
        reservation.payment_status = "paid"
        existing = db.scalar(
            select(Ticket).where(Ticket.reservation_id == reservation.id)
        )
        if existing:
            tickets.append(existing)
        else:
            ticket, _ = build_ticket(db, reservation, event, checkout.user_id)
            tickets.append(ticket)

    checkout.status = "paid"
    checkout.provider_payment_id = provider_payment_id
    return tickets


def tickets_for_checkout(db: Session, checkout_id: str) -> list[Ticket]:
    return list(
        db.scalars(
            select(Ticket)
            .join(Reservation, Reservation.id == Ticket.reservation_id)
            .join(
                CheckoutReservation,
                CheckoutReservation.reservation_id == Reservation.id,
            )
            .where(CheckoutReservation.checkout_id == checkout_id)
            .order_by(Ticket.id)
        ).all()
    )


def checkout_to_out(db: Session, checkout: PaymentCheckout) -> CheckoutOut:
    event = db.get(Event, checkout.event_id)
    reservations = reservations_for_checkout(db, checkout.id)
    seat_ids = [reservation.seat_id for reservation in reservations]
    seats = {
        seat.id: seat
        for seat in db.scalars(select(Seat).where(Seat.id.in_(seat_ids))).all()
    }
    labels = [seats[reservation.seat_id].label for reservation in reservations]
    ticket_ids = [ticket.id for ticket in tickets_for_checkout(db, checkout.id)]
    return CheckoutOut(
        id=checkout.id,
        status=checkout.status,
        checkout_url=checkout.checkout_url if checkout.status == "pending" else None,
        event_id=checkout.event_id,
        event_title=event.title if event else "Evento removido",
        event_type=event.event_type if event else "unknown",
        quantity=len(reservations),
        seat_labels=[] if event and event.event_type == "show" else labels,
        amount_cents=checkout.amount_cents,
        currency=checkout.currency,
        expires_at=checkout.expires_at,
        ticket_ids=ticket_ids,
    )


def available_count(db: Session, event_id: int) -> int:
    return db.scalar(
        select(func.count(Seat.id)).where(
            Seat.event_id == event_id,
            Seat.status == "available",
        )
    ) or 0
