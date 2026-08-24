import asyncio
from datetime import datetime, time, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.event_time import APP_TIMEZONE, is_event_from_previous_day
from app.main import reserve_batch, validate_ticket
from app.models import Event, Reservation, Seat, Ticket, User
from app.schemas import GateValidationIn, ReservationBatchCreate
from app.services import build_ticket


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


def local_day_start(day_offset: int = 0) -> datetime:
    local_date = datetime.now(APP_TIMEZONE).date() + timedelta(days=day_offset)
    return datetime.combine(local_date, time.min, tzinfo=APP_TIMEZONE).astimezone(
        timezone.utc
    )


def create_event_context(
    db: Session,
    *,
    starts_at: datetime,
    event_type: str = "movie",
) -> tuple[User, User, Event, Seat]:
    organizer = User(
        name="Organizador",
        email=f"organizer-{starts_at.timestamp()}@teste.dev",
        password_hash="test",
        role="organizer",
    )
    client = User(
        name="Cliente",
        email=f"client-{starts_at.timestamp()}@teste.dev",
        password_hash="test",
        role="client",
    )
    gate = User(
        name="Portaria",
        email=f"gate-{starts_at.timestamp()}@teste.dev",
        password_hash="test",
        role="gate",
    )
    db.add_all([organizer, client, gate])
    db.flush()

    event = Event(
        title="Evento com regra de data",
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
    return client, gate, event, seat


def create_ticket(
    db: Session,
    client: User,
    event: Event,
    seat: Seat,
) -> tuple[Ticket, str]:
    seat.status = "reserved"
    reservation = Reservation(
        event_id=event.id,
        seat_id=seat.id,
        user_id=client.id,
        status="confirmed",
        payment_status="paid",
    )
    db.add(reservation)
    db.flush()
    ticket, token = build_ticket(db, reservation, event, client.id)
    db.commit()
    db.refresh(ticket)
    return ticket, token


def reserve_one(db: Session, client: User, seat: Seat):
    return asyncio.run(
        reserve_batch(
            ReservationBatchCreate(seat_ids=[seat.id], payment="approve"),
            client,
            db,
        )
    )


def test_calendar_rule_uses_sao_paulo_day_boundary():
    now = datetime(2026, 8, 24, 1, 0, tzinfo=timezone.utc)
    previous_local_day = datetime(2026, 8, 23, 2, 59, tzinfo=timezone.utc)
    same_local_day = datetime(2026, 8, 23, 3, 0, tzinfo=timezone.utc)

    assert is_event_from_previous_day(previous_local_day, now=now)
    assert not is_event_from_previous_day(same_local_day, now=now)


def test_client_cannot_reserve_event_from_previous_day(db: Session):
    client, _, _, seat = create_event_context(db, starts_at=local_day_start(-1))

    with pytest.raises(HTTPException) as exc_info:
        reserve_one(db, client, seat)

    assert exc_info.value.status_code == 409
    assert "dias anteriores" in exc_info.value.detail
    assert db.get(Seat, seat.id).status == "available"
    assert list(db.scalars(select(Reservation)).all()) == []
    assert list(db.scalars(select(Ticket)).all()) == []


def test_client_can_reserve_event_from_current_day(db: Session):
    client, _, _, seat = create_event_context(db, starts_at=local_day_start())

    result = reserve_one(db, client, seat)

    assert result[0].status == "confirmed"
    assert result[0].ticket_id is not None
    assert db.get(Seat, seat.id).status == "reserved"


@pytest.mark.parametrize("event_type", ["movie", "show"])
def test_gate_cannot_validate_ticket_from_previous_day(
    db: Session,
    event_type: str,
):
    client, gate, event, seat = create_event_context(
        db,
        starts_at=local_day_start(-1),
        event_type=event_type,
    )
    ticket, token = create_ticket(db, client, event, seat)

    result = validate_ticket(
        GateValidationIn(code=token, event_id=event.id),
        gate,
        db,
    )

    assert result.result == "invalid"
    assert "dias anteriores" in result.message
    assert ticket.status == "valid"
    assert ticket.used_at is None


@pytest.mark.parametrize("event_type", ["movie", "show"])
@pytest.mark.parametrize("day_offset", [0, 1])
def test_gate_can_validate_ticket_from_current_or_future_day(
    db: Session,
    day_offset: int,
    event_type: str,
):
    client, gate, event, seat = create_event_context(
        db,
        starts_at=local_day_start(day_offset),
        event_type=event_type,
    )
    ticket, token = create_ticket(db, client, event, seat)

    result = validate_ticket(
        GateValidationIn(code=token, event_id=event.id),
        gate,
        db,
    )

    assert result.result == "valid"
    assert ticket.status == "used"
    assert ticket.used_at is not None
