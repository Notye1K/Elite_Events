from datetime import datetime, timezone
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
        "starts_at": datetime.now(timezone.utc),
        "location": "Local",
        "capacity": 10,
        "price_cents": 1000,
        "image_url": image_url,
    }

def test_event_image_url_is_optional():
    event = EventCreate(**event_payload())
    assert event.image_url is None

def test_event_image_url_must_be_http_url():
    with pytest.raises(ValueError):
        EventCreate(**event_payload("imagem-invalida"))
