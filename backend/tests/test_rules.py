from datetime import datetime, timezone
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
