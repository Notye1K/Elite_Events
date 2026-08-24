import os
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.db import Base
from app.main import validate_ticket
from app.models import Event, Reservation, Seat, Ticket, User
from app.schemas import GateValidationIn
from app.services import build_ticket


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL não configurada para o teste concorrente PostgreSQL",
)
def test_gate_accepts_only_one_of_two_simultaneous_validations():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    suffix = uuid4().hex

    with Session(engine) as db:
        organizer = User(
            name="Organizador concorrência",
            email=f"organizer-{suffix}@teste.dev",
            password_hash="test",
            role="organizer",
        )
        client = User(
            name="Cliente concorrência",
            email=f"client-{suffix}@teste.dev",
            password_hash="test",
            role="client",
        )
        gate = User(
            name="Portaria concorrência",
            email=f"gate-{suffix}@teste.dev",
            password_hash="test",
            role="gate",
        )
        db.add_all([organizer, client, gate])
        db.flush()
        event = Event(
            title=f"Evento concorrência {suffix}",
            description="Validação simultânea de ingresso",
            event_type="movie",
            starts_at=datetime.now(timezone.utc) + timedelta(days=1),
            location="Sala de teste",
            capacity=1,
            price_cents=0,
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
            status="reserved",
        )
        db.add(seat)
        db.flush()
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
        ids = {
            "organizer": organizer.id,
            "client": client.id,
            "gate": gate.id,
            "event": event.id,
            "seat": seat.id,
            "reservation": reservation.id,
            "ticket": ticket.id,
        }

    barrier = threading.Barrier(2)
    results: list[str] = []
    failures: list[Exception] = []

    def validate_at_the_same_time():
        try:
            with Session(engine) as db:
                gate_user = db.get(User, ids["gate"])
                barrier.wait(timeout=5)
                result = validate_ticket(
                    GateValidationIn(code=token, event_id=ids["event"]),
                    gate_user,
                    db,
                )
                results.append(result.result)
        except Exception as exc:
            failures.append(exc)

    threads = [threading.Thread(target=validate_at_the_same_time) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    try:
        assert all(not thread.is_alive() for thread in threads)
        assert failures == []
        assert sorted(results) == ["already_used", "valid"]
    finally:
        with Session(engine) as db:
            db.execute(delete(Ticket).where(Ticket.id == ids["ticket"]))
            db.execute(
                delete(Reservation).where(Reservation.id == ids["reservation"])
            )
            db.execute(delete(Seat).where(Seat.id == ids["seat"]))
            db.execute(delete(Event).where(Event.id == ids["event"]))
            db.execute(
                delete(User).where(
                    User.id.in_([ids["organizer"], ids["client"], ids["gate"]])
                )
            )
            db.commit()
        engine.dispose()
