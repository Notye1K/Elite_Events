from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from .db import initialize_database, SessionLocal
from .models import Event, User
from .security import hash_password
from .services import create_event_seats

USERS = [
    ("Ana Organizadora", "organizador@elite.dev", "123456", "organizer"),
    ("Carlos Cliente", "cliente1@elite.dev", "123456", "client"),
    ("Diana Cliente", "cliente2@elite.dev", "123456", "client"),
    ("Equipe Portaria", "portaria@elite.dev", "123456", "gate"),
]

def run():
    initialize_database()
    db = SessionLocal()
    try:
        users = {}
        for name, email, password, role in USERS:
            user = db.scalar(select(User).where(User.email == email))
            if not user:
                user = User(name=name, email=email, password_hash=hash_password(password), role=role)
                db.add(user); db.flush()
            users[role] = user
        if not db.scalar(select(Event).where(Event.title == "Noite de Cinema Elite")):
            event = Event(
                title="Noite de Cinema Elite", description="Evento semeado para avaliação ponta a ponta.",
                event_type="seated", starts_at=datetime.now(timezone.utc) + timedelta(days=14),
                location="Cinema Central — Sala 01", capacity=40, price_cents=3500, published=True,
                organizer_id=users["organizer"].id, external_source="tmdb", external_id="seed",
            )
            db.add(event); db.flush(); create_event_seats(db, event)
        db.commit()
        print("Seed complete")
    finally:
        db.close()

if __name__ == "__main__":
    run()
