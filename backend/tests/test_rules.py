from datetime import datetime, timedelta, timezone
import pytest
from app.schemas import EventCreate
from app.security import create_ticket_token, decode_ticket_token, token_hash

def test_ticket_token_is_signed_and_tamper_evident(monkeypatch):
    token = create_ticket_token(10, 20, "abc")
    payload = decode_ticket_token(token)
    assert payload["ticket_id"] == 10
    assert payload["event_id"] == 20
    assert token_hash(token) != token_hash(token + "x")

def test_ticket_payload_has_required_identity():
    token = create_ticket_token(1, 2, "jti")
    payload = decode_ticket_token(token)
    assert set(["ticket_id", "event_id", "jti", "iat"]).issubset(payload)

def event_payload(image_url=None):
    return {
        "title": "Evento",
        "description": "Descrição",
        "starts_at": datetime.now(timezone.utc) + timedelta(hours=25),
        "location": "Local",
        "capacity": 200,
        "price_cents": 1000,
        "image_url": image_url,
    }

def test_event_image_url_is_optional():
    event = EventCreate(**event_payload())
    assert event.image_url is None

def test_event_image_url_must_be_http_url():
    with pytest.raises(ValueError):
        EventCreate(**event_payload("imagem-invalida"))

def test_movie_has_fixed_capacity_of_two_hundred_seats():
    payload = event_payload()
    payload["capacity"] = 199
    with pytest.raises(ValueError):
        EventCreate(**payload)

def test_show_requires_capacity_and_accepts_custom_value():
    payload = event_payload()
    payload.update({"event_type": "show", "capacity": 350})
    event = EventCreate(**payload)
    assert event.capacity == 350

def test_ticketmaster_is_an_allowed_external_source():
    payload = event_payload()
    payload.update({"event_type": "show", "external_source": "ticketmaster"})
    event = EventCreate(**payload)
    assert event.external_source == "ticketmaster"

@pytest.mark.parametrize(
    ("event_type", "external_source"),
    [("movie", "ticketmaster"), ("show", "tmdb")],
)
def test_external_source_must_match_event_type(event_type, external_source):
    payload = event_payload()
    payload.update(
        {
            "event_type": event_type,
            "capacity": 200 if event_type == "movie" else 300,
            "external_source": external_source,
        }
    )
    with pytest.raises(ValueError):
        EventCreate(**payload)

def test_event_requires_at_least_24_hours_notice():
    payload = event_payload()
    payload["starts_at"] = datetime.now(timezone.utc) + timedelta(hours=23)
    with pytest.raises(ValueError):
        EventCreate(**payload)

def test_event_cannot_be_more_than_ten_years_away():
    payload = event_payload()
    payload["starts_at"] = datetime.now(timezone.utc) + timedelta(days=3651)
    with pytest.raises(ValueError):
        EventCreate(**payload)

@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "x" * 256),
        ("description", "x" * 5001),
        ("image_url", "https://example.com/" + "x" * 500),
        ("location", "x" * 256),
        ("capacity", 1001),
        ("price_cents", 10_000_001),
        ("external_id", "x" * 121),
    ],
)
def test_event_fields_reject_values_above_their_limits(field, value):
    payload = event_payload()
    payload[field] = value
    with pytest.raises(ValueError):
        EventCreate(**payload)
