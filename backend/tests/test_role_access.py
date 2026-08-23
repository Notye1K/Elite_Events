from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.deps import current_user
from app.main import app
from app.models import Event, Seat, User


@pytest.fixture
def access_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        users = {
            role: User(
                name=role,
                email=f"{role}-access@teste.dev",
                password_hash="test",
                role=role,
            )
            for role in ("client", "organizer", "gate")
        }
        db.add_all(users.values())
        db.flush()

        event = Event(
            title="Evento público",
            description="Descrição",
            event_type="seated",
            starts_at=datetime.now(timezone.utc) + timedelta(days=2),
            location="Local",
            capacity=1,
            price_cents=1000,
            published=True,
            organizer_id=users["organizer"].id,
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

        def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        api_client = TestClient(app)
        try:
            yield api_client, users, event, seat
        finally:
            api_client.close()
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=engine)


def authenticate_as(user: User | None):
    if user is None:
        app.dependency_overrides.pop(current_user, None)
        return

    def override_user():
        return user

    app.dependency_overrides[current_user] = override_user


def test_events_and_seats_are_public_for_every_role(access_context):
    api_client, users, event, _ = access_context

    for user in (None, *users.values()):
        authenticate_as(user)
        assert api_client.get("/events").status_code == 200
        assert api_client.get(f"/events/{event.id}").status_code == 200
        assert api_client.get(f"/events/{event.id}/seats").status_code == 200


@pytest.mark.parametrize(
    ("method", "path", "payload", "allowed_role"),
    [
        ("get", "/tickets", None, "client"),
        ("get", "/organizer/events", None, "organizer"),
        (
            "post",
            "/gate/validate",
            {"code": "invalid", "event_id": 1},
            "gate",
        ),
    ],
)
def test_private_endpoints_allow_only_their_role(
    access_context,
    method,
    path,
    payload,
    allowed_role,
):
    api_client, users, _, _ = access_context

    authenticate_as(None)
    anonymous_response = api_client.request(method, path, json=payload)
    assert anonymous_response.status_code == 401

    for role, user in users.items():
        authenticate_as(user)
        response = api_client.request(method, path, json=payload)
        expected_status = 200 if role == allowed_role else 403
        assert response.status_code == expected_status


def test_only_client_can_purchase_tickets(access_context):
    api_client, users, _, seat = access_context
    payload = {"seat_ids": [seat.id], "payment": "decline"}

    authenticate_as(None)
    assert api_client.post("/reservations/batch", json=payload).status_code == 401

    for role in ("organizer", "gate"):
        authenticate_as(users[role])
        assert api_client.post("/reservations/batch", json=payload).status_code == 403

    authenticate_as(users["client"])
    response = api_client.post("/reservations/batch", json=payload)
    assert response.status_code == 200
    assert response.json()[0]["status"] == "cancelled"
