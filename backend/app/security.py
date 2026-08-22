from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import jwt
from passlib.context import CryptContext
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": now + timedelta(minutes=settings.jwt_exp_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def create_ticket_token(ticket_id: int, event_id: int, jti: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"ticket_id": ticket_id, "event_id": event_id, "jti": jti, "iat": now}
    return jwt.encode(payload, settings.ticket_secret, algorithm="HS256")


def decode_ticket_token(token: str) -> dict:
    return jwt.decode(token, settings.ticket_secret, algorithms=["HS256"])


def token_hash(token: str) -> str:
    return hmac.new(settings.ticket_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
