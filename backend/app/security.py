from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import bcrypt
import jwt
from .config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(minutes=settings.jwt_exp_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def create_ticket_token(
    ticket_id: int,
    event_id: int,
    jti: str,
    issued_at: datetime | None = None,
) -> str:
    issued_at = issued_at or datetime.now(timezone.utc)
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    payload = {
        "ticket_id": ticket_id,
        "event_id": event_id,
        "jti": jti,
        "iat": int(issued_at.timestamp()),
    }
    return jwt.encode(payload, settings.ticket_secret, algorithm="HS256")


def decode_ticket_token(token: str) -> dict:
    return jwt.decode(token, settings.ticket_secret, algorithms=["HS256"])


def token_hash(token: str) -> str:
    return hmac.new(settings.ticket_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
