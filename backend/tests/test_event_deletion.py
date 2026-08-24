from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import delete_event
from app.models import Event, Reservation, Seat, Ticket, User


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


def create_user(db: Session, email: str, role: str) -> User:
    user = User(
        name=email.split("@")[0],
        email=email,
        password_hash="test",
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def create_event_with_seat(
    db: Session,
    organizer: User,
    starts_at: datetime,
    event_type: str,
) -> tuple[Event, Seat]:
    event = Event(
        title="Evento de teste",
        description="Descrição",
        event_type=event_type,
        starts_at=starts_at,
        location="Local",
        capacity=1,
        price_cents=1000,
        published=True,
        organizer_id=organizer.id,
    )
    db.add(event)
    db.flush()
    seat = Seat(
        event_id=event.id,
        label="A1",
        row="A",
        number=1,
        status="available",
    )
    db.add(seat)
    db.commit()
    return event, seat


def create_reservation(
    db: Session,
    event: Event,
    seat: Seat,
    client: User,
) -> Reservation:
    seat.status = "reserved"
    reservation = Reservation(
        event_id=event.id,
        seat_id=seat.id,
        user_id=client.id,
        status="confirmed",
        payment_status="paid",
    )
    db.add(reservation)
    db.commit()
    return reservation


@pytest.mark.parametrize("event_type", ["movie", "show"])
def test_organizer_can_delete_own_future_event_without_reservations(
    db: Session,
    event_type: str,
):
    organizer = create_user(db, "organizer@teste.dev", "organizer")
    event, _ = create_event_with_seat(
        db,
        organizer,
        datetime.now(timezone.utc) + timedelta(days=2),
        event_type,
    )
    event_id = event.id

    delete_event(event_id, organizer, db)

    assert db.get(Event, event_id) is None


@pytest.mark.parametrize("event_type", ["movie", "show"])
def test_organizer_cannot_delete_another_organizers_event(
    db: Session,
    event_type: str,
):
    owner = create_user(db, "owner@teste.dev", "organizer")
    another_organizer = create_user(db, "another@teste.dev", "organizer")
    event, _ = create_event_with_seat(
        db,
        owner,
        datetime.now(timezone.utc) + timedelta(days=2),
        event_type,
    )

    with pytest.raises(HTTPException) as exc_info:
        delete_event(event.id, another_organizer, db)

    assert exc_info.value.status_code == 403
    assert db.get(Event, event.id) is not None


@pytest.mark.parametrize("event_type", ["movie", "show"])
def test_organizer_can_delete_past_event_with_reservations(
    db: Session,
    event_type: str,
):
    organizer = create_user(db, "organizer@teste.dev", "organizer")
    client = create_user(db, "client@teste.dev", "client")
    event, seat = create_event_with_seat(
        db,
        organizer,
        datetime.now(timezone.utc) - timedelta(hours=1),
        event_type,
    )
    reservation = create_reservation(db, event, seat, client)
    ticket = Ticket(
        reservation_id=reservation.id,
        event_id=event.id,
        user_id=client.id,
        code_jti="past-event-ticket",
        token_hash="hash",
        status="used",
    )
    db.add(ticket)
    db.commit()
    event_id = event.id

    delete_event(event_id, organizer, db)

    assert db.get(Event, event_id) is None
    assert db.scalar(select(Reservation).where(Reservation.event_id == event_id)) is None
    assert db.scalar(select(Ticket).where(Ticket.event_id == event_id)) is None


@pytest.mark.parametrize("event_type", ["movie", "show"])
def test_organizer_cannot_delete_future_event_with_reservation(
    db: Session,
    event_type: str,
):
    organizer = create_user(db, "organizer@teste.dev", "organizer")
    client = create_user(db, "client@teste.dev", "client")
    event, seat = create_event_with_seat(
        db,
        organizer,
        datetime.now(timezone.utc) + timedelta(days=2),
        event_type,
    )
    create_reservation(db, event, seat, client)

    with pytest.raises(HTTPException) as exc_info:
        delete_event(event.id, organizer, db)

    assert exc_info.value.status_code == 409
    assert db.get(Event, event.id) is not None
