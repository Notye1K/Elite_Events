import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import (
    cancel_ticket,
    create_checkout_session,
    get_event_availability,
    my_tickets,
)
from app.models import Event, Seat, Ticket, User
from app.schemas import CheckoutCreate
from app.services import create_event_seats


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def create_event(
    db: Session,
    event_type: str,
    capacity: int = 3,
    starts_at: datetime | None = None,
):
    organizer = User(
        name="Organizador",
        email=f"organizer-{event_type}@teste.dev",
        password_hash="test",
        role="organizer",
    )
    client = User(
        name="Cliente",
        email=f"client-{event_type}@teste.dev",
        password_hash="test",
        role="client",
    )
    db.add_all([organizer, client])
    db.flush()
    event = Event(
        title="Evento",
        description="Descrição",
        event_type=event_type,
        starts_at=starts_at or datetime.now(timezone.utc) + timedelta(days=2),
        location="Local",
        capacity=capacity,
        price_cents=0,
        published=True,
        organizer_id=organizer.id,
    )
    db.add(event)
    db.flush()
    create_event_seats(db, event)
    db.commit()
    return client, event


def create_free_checkout(
    db: Session,
    client: User,
    event: Event,
    *,
    quantity: int | None = None,
    seat_ids: list[int] | None = None,
):
    return asyncio.run(
        create_checkout_session(
            CheckoutCreate(
                event_id=event.id,
                quantity=quantity,
                seat_ids=seat_ids or [],
            ),
            client,
            db,
            None,
        )
    )


def test_movie_inventory_has_twenty_seats_per_row(db: Session):
    _, event = create_event(db, "movie", capacity=200)
    seats = list(
        db.scalars(
            select(Seat).where(Seat.event_id == event.id).order_by(Seat.id)
        ).all()
    )

    assert len(seats) == 200
    assert len({seat.row for seat in seats}) == 10
    assert all(1 <= seat.number <= 20 for seat in seats)


def test_show_purchase_decreases_general_inventory_and_hides_seat(db: Session):
    client, event = create_event(db, "show")

    checkout = create_free_checkout(db, client, event, quantity=2)

    availability = get_event_availability(event.id, db)
    tickets = my_tickets(client, db)
    assert checkout.quantity == 2
    assert checkout.status == "paid"
    assert availability.available == 1
    assert len(list(db.scalars(select(Ticket)).all())) == 2
    assert all(ticket.event_type == "show" for ticket in tickets)
    assert all(ticket.seat_label is None for ticket in tickets)


def test_cancelling_show_ticket_returns_one_unit_to_inventory(db: Session):
    client, event = create_event(db, "show")
    checkout = create_free_checkout(db, client, event, quantity=1)
    ticket_id = checkout.ticket_ids[0]

    asyncio.run(cancel_ticket(ticket_id, client, db))

    assert get_event_availability(event.id, db).available == event.capacity


def test_show_purchase_is_atomic_when_inventory_is_insufficient(db: Session):
    client, event = create_event(db, "show")

    with pytest.raises(HTTPException) as exc_info:
        create_free_checkout(db, client, event, quantity=4)

    assert exc_info.value.status_code == 409
    assert get_event_availability(event.id, db).available == event.capacity
    assert list(db.scalars(select(Ticket)).all()) == []


def test_show_from_previous_day_cannot_be_purchased(db: Session):
    client, event = create_event(
        db,
        "show",
        starts_at=datetime.now(timezone.utc) - timedelta(days=2),
    )

    with pytest.raises(HTTPException) as exc_info:
        create_free_checkout(db, client, event, quantity=1)

    assert exc_info.value.status_code == 409
    assert get_event_availability(event.id, db).available == event.capacity


def test_show_cannot_be_purchased_by_internal_inventory_id(db: Session):
    client, event = create_event(db, "show")
    seat = db.scalar(select(Seat).where(Seat.event_id == event.id))

    with pytest.raises(HTTPException) as exc_info:
        create_free_checkout(db, client, event, seat_ids=[seat.id])

    assert exc_info.value.status_code == 400


def test_movie_cannot_be_purchased_as_general_admission(db: Session):
    client, event = create_event(db, "movie", capacity=200)

    with pytest.raises(HTTPException) as exc_info:
        create_free_checkout(db, client, event, quantity=1)

    assert exc_info.value.status_code == 400
