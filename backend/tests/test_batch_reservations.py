import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import cancel_ticket, my_tickets, reserve_batch, share_ticket
from app.models import Event, Reservation, Seat, Ticket, User
from app.schemas import ReservationBatchCreate
from app.security import token_hash


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


def create_event_with_seats(db: Session) -> tuple[User, list[Seat]]:
    organizer = User(
        name="Organizador",
        email="organizer-batch@teste.dev",
        password_hash="test",
        role="organizer",
    )
    client = User(
        name="Cliente",
        email="client-batch@teste.dev",
        password_hash="test",
        role="client",
    )
    db.add_all([organizer, client])
    db.flush()

    event = Event(
        title="Evento em grupo",
        description="Descrição",
        event_type="seated",
        starts_at=datetime.now(timezone.utc) + timedelta(days=2),
        location="Local",
        capacity=3,
        price_cents=1000,
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
        for number in range(1, 4)
    ]
    db.add_all(seats)
    db.commit()
    return client, seats


def run_batch(
    db: Session,
    client: User,
    seats: list[Seat],
    payment: str,
):
    payload = ReservationBatchCreate(
        seat_ids=[seat.id for seat in seats],
        payment=payment,
    )
    return asyncio.run(reserve_batch(payload, client, db))


def test_batch_reservation_approves_all_seats_and_creates_one_ticket_each(db: Session):
    client, seats = create_event_with_seats(db)

    results = run_batch(db, client, seats[:2], "approve")

    assert len(results) == 2
    assert all(result.status == "confirmed" for result in results)
    assert all(result.payment_status == "paid" for result in results)
    assert all(result.ticket_id is not None for result in results)
    assert all(db.get(Seat, seat.id).status == "reserved" for seat in seats[:2])
    assert len(list(db.scalars(select(Ticket)).all())) == 2


def test_batch_reservation_decline_returns_every_seat_to_stock(db: Session):
    client, seats = create_event_with_seats(db)

    results = run_batch(db, client, seats[:2], "decline")

    assert len(results) == 2
    assert all(result.status == "cancelled" for result in results)
    assert all(result.payment_status == "declined" for result in results)
    assert all(db.get(Seat, seat.id).status == "available" for seat in seats[:2])
    assert list(db.scalars(select(Ticket)).all()) == []


def test_batch_reservation_is_atomic_when_one_seat_is_unavailable(db: Session):
    client, seats = create_event_with_seats(db)
    seats[1].status = "reserved"
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        run_batch(db, client, seats[:2], "approve")

    assert exc_info.value.status_code == 409
    assert db.get(Seat, seats[0].id).status == "available"
    assert list(db.scalars(select(Reservation)).all()) == []
    assert list(db.scalars(select(Ticket)).all()) == []


def test_listed_ticket_has_stable_token_and_valid_shared_link(db: Session):
    client, seats = create_event_with_seats(db)
    run_batch(db, client, seats[:1], "approve")
    ticket = db.scalar(select(Ticket))

    ticket.token_hash = "legacy-token-hash"
    db.commit()

    first_listing = my_tickets(client, db)
    second_listing = my_tickets(client, db)
    shared_ticket = share_ticket(first_listing[0].token, db)

    assert first_listing[0].token == second_listing[0].token
    assert ticket.token_hash == token_hash(first_listing[0].token)
    assert shared_ticket.id == ticket.id
    assert shared_ticket.token == first_listing[0].token


def test_client_can_cancel_own_valid_ticket(db: Session):
    client, seats = create_event_with_seats(db)
    run_batch(db, client, seats[:1], "approve")
    ticket = db.scalar(select(Ticket))
    reservation = db.get(Reservation, ticket.reservation_id)

    result = asyncio.run(cancel_ticket(ticket.id, client, db))

    assert result.status == "cancelled"
    assert result.payment_status == "refunded"
    assert ticket.status == "cancelled"
    assert reservation.status == "cancelled"
    assert db.get(Seat, seats[0].id).status == "available"


def test_client_cannot_cancel_another_clients_ticket(db: Session):
    owner, seats = create_event_with_seats(db)
    run_batch(db, owner, seats[:1], "approve")
    ticket = db.scalar(select(Ticket))
    another_client = User(
        name="Outro cliente",
        email="another-client@teste.dev",
        password_hash="test",
        role="client",
    )
    db.add(another_client)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(cancel_ticket(ticket.id, another_client, db))

    assert exc_info.value.status_code == 404
    assert ticket.status == "valid"
    assert db.get(Seat, seats[0].id).status == "reserved"


def test_client_cannot_cancel_used_ticket(db: Session):
    client, seats = create_event_with_seats(db)
    run_batch(db, client, seats[:1], "approve")
    ticket = db.scalar(select(Ticket))
    ticket.status = "used"
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(cancel_ticket(ticket.id, client, db))

    assert exc_info.value.status_code == 409
    assert ticket.status == "used"
    assert db.get(Seat, seats[0].id).status == "reserved"
