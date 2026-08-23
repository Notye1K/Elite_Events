import secrets
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .models import Event, Reservation, Seat, Ticket
from .security import create_ticket_token, token_hash


def create_event_seats(db: Session, event: Event):
    # Seat map optional implemented as 10 seats across 10 rows when using seated events.
    if event.event_type != "seated":
        return
    seats_per_row = 10
    rows = max(1, (event.capacity + seats_per_row - 1) // seats_per_row)
    created = 0
    for row_index in range(rows):
        row = chr(ord("A") + row_index)
        for number in range(1, seats_per_row + 1):
            if created >= event.capacity:
                break
            db.add(Seat(event_id=event.id, label=f"{row}{number}", row=row, number=number))
            created += 1


def build_ticket(db: Session, reservation: Reservation, event: Event, user_id: int) -> tuple[Ticket, str]:
    jti = secrets.token_hex(16)
    ticket = Ticket(
        reservation_id=reservation.id,
        event_id=event.id,
        user_id=user_id,
        code_jti=jti,
        token_hash="pending",
    )
    db.add(ticket)
    db.flush()
    token = create_ticket_token(ticket.id, event.id, jti, ticket.created_at)
    ticket.token_hash = token_hash(token)
    return ticket, token


def catalog_search(source: str, query: str):
    if source == "tmdb":
        if not settings.tmdb_api_key:
            return {
                "source": source,
                "configured": False,
                "items": []
            }

        url = "https://api.themoviedb.org/3/search/movie"

        headers = {
            "Authorization": f"Bearer {settings.tmdb_api_key}",
            "accept": "application/json",
        }

        params = {
            "query": query,
            "include_adult": False,
            "language": "pt-BR",
            "page": 1,
            "region": "BR",
        }

        response = httpx.get(
            url,
            headers=headers,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        return {
            "source": source,
            "configured": True,
            "items": [
                {
                    "id": str(movie.get("id")),
                    "title": movie.get("title"),
                    "original_title": movie.get("original_title"),
                    "overview": movie.get("overview"),
                    "date": movie.get("release_date"),
                    "image": (
                        f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
                        if movie.get("poster_path")
                        else None
                    ),
                    "vote_average": movie.get("vote_average"),
                }
                for movie in data.get("results", [])[:12]
            ],
        }
    raise ValueError("Unknown catalog source")
