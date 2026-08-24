from datetime import datetime, timezone
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db, initialize_database
from .deps import current_user, role_required
from .event_time import is_event_from_previous_day
from .models import Event, Reservation, Seat, Ticket, User
from .schemas import *
from .security import create_access_token, decode_ticket_token, hash_password, token_hash, verify_password
from .services import build_ticket, catalog_search, create_event_seats

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, list[WebSocket]] = {}
    async def connect(self, event_id: int, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(event_id, []).append(ws)
    def disconnect(self, event_id: int, ws: WebSocket):
        if event_id in self.connections and ws in self.connections[event_id]:
            self.connections[event_id].remove(ws)
    async def broadcast(self, event_id: int, payload: dict):
        stale = []
        for ws in self.connections.get(event_id, []):
            try:
                await ws.send_json(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(event_id, ws)

manager = ConnectionManager()

def event_data(payload: EventCreate):
    data = payload.model_dump()
    data["image_url"] = str(payload.image_url) if payload.image_url else None
    return data

@app.on_event("startup")
def startup():
    initialize_database()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/register", response_model=TokenOut)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    role = payload.role if payload.role in {"client", "organizer", "gate"} else "client"
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(409, "Email already registered")
    user = User(name=payload.name, email=payload.email.lower(), password_hash=hash_password(payload.password), role=role)
    db.add(user); db.commit(); db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id, user.role), user=user)

@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return TokenOut(access_token=create_access_token(user.id, user.role), user=user)

@app.get("/events", response_model=list[EventOut])
def list_events(q: str | None = Query(default=None), db: Session = Depends(get_db)):
    stmt = select(Event).where(Event.published.is_(True)).order_by(Event.starts_at)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Event.title.ilike(like), Event.location.ilike(like)))
    return list(db.scalars(stmt).all())

@app.get("/events/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    return event

@app.get("/events/{event_id}/seats", response_model=list[SeatOut])
def get_seats(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event.event_type == "show":
        return []
    return list(db.scalars(select(Seat).where(Seat.event_id == event_id).order_by(Seat.row, Seat.number)).all())

@app.get("/events/{event_id}/availability", response_model=EventAvailabilityOut)
def get_event_availability(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    available = db.scalar(
        select(func.count(Seat.id)).where(
            Seat.event_id == event.id,
            Seat.status == "available",
        )
    ) or 0
    return EventAvailabilityOut(capacity=event.capacity, available=available)

@app.post("/organizer/events", response_model=EventOut)
def create_event(payload: EventCreate, user: User = Depends(role_required("organizer")), db: Session = Depends(get_db)):
    event = Event(**event_data(payload), organizer_id=user.id)
    db.add(event); db.flush(); create_event_seats(db, event); db.commit(); db.refresh(event)
    return event

@app.get("/organizer/events", response_model=list[EventOut])
def organizer_events(user: User = Depends(role_required("organizer")), db: Session = Depends(get_db)):
    return list(db.scalars(select(Event).where(Event.organizer_id == user.id).order_by(Event.starts_at)).all())

@app.patch("/organizer/events/{event_id}", response_model=EventOut)
def update_event(event_id: int, payload: EventCreate, user: User = Depends(role_required("organizer")), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event or event.organizer_id != user.id:
        raise HTTPException(404, "Event not found")
    for k, v in event_data(payload).items():
        setattr(event, k, v)
    db.commit(); db.refresh(event)
    return event

@app.delete("/organizer/events/{event_id}")
def delete_event(event_id: int, user: User = Depends(role_required("organizer")), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Evento não encontrado.")
    if event.organizer_id != user.id:
        raise HTTPException(403, "Você só pode excluir seus próprios eventos.")

    starts_at = event.starts_at
    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    is_past_event = starts_at <= datetime.now(timezone.utc)

    if not is_past_event:
        active_reservation = db.scalar(
            select(Reservation.id)
            .where(
                Reservation.event_id == event.id,
                Reservation.status.in_(("pending", "confirmed")),
            )
            .limit(1)
        )
        if active_reservation:
            raise HTTPException(
                409,
                "Eventos futuros com reservas ativas não podem ser excluídos.",
            )

    db.execute(delete(Ticket).where(Ticket.event_id == event.id))
    db.execute(delete(Reservation).where(Reservation.event_id == event.id))
    db.delete(event)
    db.commit()
    return {"message": "Evento excluído com sucesso."}

@app.get("/external/catalog")
def external_catalog(source: str = Query(pattern="^(tmdb|ticketmaster)$"), q: str = Query(min_length=1, max_length=200)):
    try:
        return catalog_search(source, q)
    except Exception as exc:
        raise HTTPException(502, f"External catalog error: {exc}") from exc

def reservation_to_out(reservation: Reservation, ticket_id: int | None = None):
    return ReservationOut(id=reservation.id, status=reservation.status, payment_status=reservation.payment_status, ticket_id=ticket_id)

async def reserve_seats(
    seat_ids: list[int],
    payment: str,
    user: User,
    db: Session,
    *,
    general_admission: bool = False,
) -> list[ReservationOut]:
    ordered_seat_ids = sorted(seat_ids)
    seats = list(
        db.scalars(
            select(Seat)
            .where(Seat.id.in_(ordered_seat_ids))
            .order_by(Seat.id)
            .with_for_update()
        ).all()
    )
    if len(seats) != len(ordered_seat_ids) or any(
        seat.status != "available" for seat in seats
    ):
        raise HTTPException(409, "Um ou mais assentos não estão mais disponíveis.")

    event_ids = {seat.event_id for seat in seats}
    if len(event_ids) != 1:
        raise HTTPException(400, "Todos os assentos devem pertencer ao mesmo evento.")

    event = db.get(Event, seats[0].event_id)
    if not event or not event.published:
        raise HTTPException(404, "Evento não encontrado.")
    if event.event_type == "show" and not general_admission:
        raise HTTPException(400, "Shows devem ser reservados pela quantidade de ingressos.")
    if event.event_type != "show" and general_admission:
        raise HTTPException(400, "Este evento utiliza seleção de assentos.")
    if is_event_from_previous_day(event.starts_at):
        raise HTTPException(
            409,
            "Não é possível reservar ingressos para eventos de dias anteriores.",
        )

    reservations_with_tickets: list[tuple[Reservation, Ticket | None]] = []
    for seat in seats:
        reservation = Reservation(
            event_id=event.id,
            seat_id=seat.id,
            user_id=user.id,
            status="pending",
            payment_status="pending",
        )
        db.add(reservation)
        seat.status = "reserved"
        db.flush()

        if payment == "decline":
            reservation.status = "cancelled"
            reservation.payment_status = "declined"
            seat.status = "available"
            ticket = None
        else:
            reservation.status = "confirmed"
            reservation.payment_status = "paid"
            ticket, _ = build_ticket(db, reservation, event, user.id)

        reservations_with_tickets.append((reservation, ticket))

    db.commit()
    results = []
    for reservation, ticket in reservations_with_tickets:
        db.refresh(reservation)
        if ticket:
            db.refresh(ticket)
        results.append(
            reservation_to_out(reservation, ticket.id if ticket else None)
        )

    available_count = db.scalar(
        select(func.count(Seat.id)).where(
            Seat.event_id == event.id,
            Seat.status == "available",
        )
    ) or 0
    for seat in seats:
        await manager.broadcast(
            event.id,
            {
                "type": "seat_updated",
                "seat_id": seat.id,
                "status": seat.status,
                "available_count": available_count,
            },
        )

    return results

@app.post("/reservations", response_model=ReservationOut)
async def reserve(payload: ReservationCreate, user: User = Depends(role_required("client")), db: Session = Depends(get_db)):
    results = await reserve_seats([payload.seat_id], payload.payment, user, db)
    return results[0]

@app.post("/reservations/batch", response_model=list[ReservationOut])
async def reserve_batch(payload: ReservationBatchCreate, user: User = Depends(role_required("client")), db: Session = Depends(get_db)):
    return await reserve_seats(payload.seat_ids, payload.payment, user, db)

@app.post("/reservations/general", response_model=list[ReservationOut])
async def reserve_general(payload: GeneralReservationCreate, user: User = Depends(role_required("client")), db: Session = Depends(get_db)):
    event = db.get(Event, payload.event_id)
    if not event or not event.published:
        raise HTTPException(404, "Evento não encontrado.")
    if event.event_type != "show":
        raise HTTPException(400, "Este evento utiliza seleção de assentos.")
    if is_event_from_previous_day(event.starts_at):
        raise HTTPException(
            409,
            "Não é possível reservar ingressos para eventos de dias anteriores.",
        )

    inventory = list(
        db.scalars(
            select(Seat)
            .where(
                Seat.event_id == event.id,
                Seat.status == "available",
            )
            .order_by(Seat.id)
            .limit(payload.quantity)
            .with_for_update(skip_locked=True)
        ).all()
    )
    if len(inventory) != payload.quantity:
        raise HTTPException(409, "Não há ingressos suficientes disponíveis.")

    return await reserve_seats(
        [seat.id for seat in inventory],
        payload.payment,
        user,
        db,
        general_admission=True,
    )

@app.post("/reservations/{reservation_id}/cancel", response_model=ReservationOut)
async def cancel_reservation(reservation_id: int, user: User = Depends(role_required("client")), db: Session = Depends(get_db)):
    reservation = db.get(Reservation, reservation_id)
    if not reservation or reservation.user_id != user.id:
        raise HTTPException(404, "Reserva não encontrada.")
    ticket = db.scalar(select(Ticket).where(Ticket.reservation_id == reservation.id))
    if reservation.status != "confirmed" or not ticket or ticket.status != "valid":
        raise HTTPException(409, "Somente ingressos válidos podem ser cancelados.")
    reservation.status = "cancelled"; reservation.payment_status = "refunded"
    seat = db.get(Seat, reservation.seat_id); seat.status = "available"
    ticket.status = "cancelled"
    db.commit()
    available_count = db.scalar(
        select(func.count(Seat.id)).where(
            Seat.event_id == reservation.event_id,
            Seat.status == "available",
        )
    ) or 0
    await manager.broadcast(
        reservation.event_id,
        {
            "type": "seat_updated",
            "seat_id": seat.id,
            "status": seat.status,
            "available_count": available_count,
        },
    )
    return reservation_to_out(reservation, ticket.id)

@app.post("/tickets/{ticket_id}/cancel", response_model=ReservationOut)
async def cancel_ticket(ticket_id: int, user: User = Depends(role_required("client")), db: Session = Depends(get_db)):
    ticket = db.get(Ticket, ticket_id)
    if not ticket or ticket.user_id != user.id:
        raise HTTPException(404, "Ingresso não encontrado.")
    return await cancel_reservation(ticket.reservation_id, user, db)

@app.get("/tickets", response_model=list[TicketOut])
def my_tickets(user: User = Depends(role_required("client")), db: Session = Depends(get_db)):
    stmt = select(Ticket, Event.title, Event.event_type, Seat.label).join(Event, Event.id == Ticket.event_id).join(Reservation, Reservation.id == Ticket.reservation_id).join(Seat, Seat.id == Reservation.seat_id).where(Ticket.user_id == user.id).order_by(Ticket.id.desc())
    rows = db.execute(stmt).all()
    out = []
    repaired_legacy_hash = False
    from .config import settings
    from .security import create_ticket_token
    for ticket, title, event_type, seat_label in rows:
        token = create_ticket_token(
            ticket.id,
            ticket.event_id,
            ticket.code_jti,
            ticket.created_at,
        )
        stable_token_hash = token_hash(token)
        if ticket.token_hash != stable_token_hash:
            ticket.token_hash = stable_token_hash
            repaired_legacy_hash = True
        out.append(TicketOut(id=ticket.id, event_id=ticket.event_id, event_title=title, event_type=event_type, seat_label=None if event_type == "show" else seat_label, token=token, status=ticket.status, share_url=f"{settings.frontend_url}/share/{token}", used_at=ticket.used_at))
    if repaired_legacy_hash:
        db.commit()
    return out

@app.get("/share/{token}", response_model=TicketOut)
def share_ticket(token: str, db: Session = Depends(get_db)):
    try:
        payload = decode_ticket_token(token)
    except Exception:
        raise HTTPException(400, "Invalid ticket")
    ticket = db.get(Ticket, int(payload["ticket_id"]))
    if not ticket or ticket.code_jti != payload["jti"] or token_hash(token) != ticket.token_hash:
        raise HTTPException(404, "Ticket not found")
    event = db.get(Event, ticket.event_id)
    reservation = db.get(Reservation, ticket.reservation_id)
    seat = db.get(Seat, reservation.seat_id)
    from .config import settings
    return TicketOut(id=ticket.id, event_id=ticket.event_id, event_title=event.title, event_type=event.event_type, seat_label=None if event.event_type == "show" else seat.label, token=token, status=ticket.status, share_url=f"{settings.frontend_url}/share/{token}", used_at=ticket.used_at)

@app.post("/gate/validate", response_model=GateValidationOut)
def validate_ticket(payload: GateValidationIn, user: User = Depends(role_required("gate")), db: Session = Depends(get_db)):
    try:
        decoded = decode_ticket_token(payload.code)
    except Exception:
        return GateValidationOut(result="invalid", message="Código inválido ou adulterado")
    ticket = db.get(Ticket, int(decoded.get("ticket_id", 0)))
    if not ticket or ticket.code_jti != decoded.get("jti") or token_hash(payload.code) != ticket.token_hash:
        return GateValidationOut(result="invalid", message="Ingresso não encontrado")
    if ticket.event_id != payload.event_id:
        return GateValidationOut(result="event_wrong", message="Ingresso pertence a outro evento", ticket_id=ticket.id)
    event = db.get(Event, ticket.event_id)
    if not event:
        return GateValidationOut(result="invalid", message="Evento não encontrado", ticket_id=ticket.id)
    if is_event_from_previous_day(event.starts_at):
        return GateValidationOut(
            result="invalid",
            message="Não é possível validar ingressos de eventos de dias anteriores",
            ticket_id=ticket.id,
        )
    if ticket.status == "used":
        return GateValidationOut(result="already_used", message="Ingresso já utilizado", ticket_id=ticket.id)
    if ticket.status != "valid":
        return GateValidationOut(result="invalid", message="Ingresso não está válido", ticket_id=ticket.id)
    ticket.status = "used"; ticket.used_at = datetime.now(timezone.utc)
    db.commit()
    return GateValidationOut(result="valid", message="Entrada autorizada", ticket_id=ticket.id)

@app.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

@app.websocket("/ws/events/{event_id}/seats")
async def seat_socket(websocket: WebSocket, event_id: int):
    await manager.connect(event_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(event_id, websocket)
