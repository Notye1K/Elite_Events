from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, UrlConstraints, field_validator, model_validator

MAX_EVENT_DESCRIPTION_LENGTH = 5_000
MAX_EVENT_PRICE_CENTS = 10_000_000
MAX_EVENT_ADVANCE_DAYS = 3_650
EventImageUrl = Annotated[AnyHttpUrl, UrlConstraints(max_length=500)]

class UserCreate(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=6)
    role: str = "client"

class LoginIn(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=MAX_EVENT_DESCRIPTION_LENGTH)
    image_url: EventImageUrl | None = None
    event_type: Literal["movie", "show"] = "movie"
    starts_at: datetime
    location: str = Field(min_length=1, max_length=255)
    capacity: int = Field(gt=0, le=1000)
    price_cents: int = Field(ge=0, le=MAX_EVENT_PRICE_CENTS)
    published: bool = False
    external_source: Literal["tmdb", "ticketmaster"] | None = None
    external_id: str | None = Field(default=None, max_length=120)

    @field_validator("title", "description", "location")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("não pode ficar em branco")
        return value

    @field_validator("starts_at")
    @classmethod
    def validate_event_date(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("deve incluir o fuso horário")

        now = datetime.now(timezone.utc)
        starts_at = value.astimezone(timezone.utc)
        if starts_at < now + timedelta(hours=24):
            raise ValueError("deve ter pelo menos 24 horas de antecedência")
        if starts_at > now + timedelta(days=MAX_EVENT_ADVANCE_DAYS):
            raise ValueError("não pode estar a mais de 10 anos no futuro")
        return value

    @model_validator(mode="after")
    def validate_capacity_for_event_type(self):
        if self.event_type == "movie" and self.capacity != 200:
            raise ValueError("filmes devem ter capacidade fixa de 200 lugares")
        if self.external_source == "tmdb" and self.event_type != "movie":
            raise ValueError("o TMDb só pode ser associado a filmes")
        if self.external_source == "ticketmaster" and self.event_type != "show":
            raise ValueError("a Ticketmaster só pode ser associada a shows")
        if self.external_id and not self.external_source:
            raise ValueError("ID externo exige uma fonte externa")
        return self

class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    image_url: str | None
    event_type: str
    starts_at: datetime
    location: str
    capacity: int
    price_cents: int
    published: bool
    organizer_id: int
    external_source: str | None
    external_id: str | None

class SeatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    row: str
    number: int
    status: str

class ReservationCreate(BaseModel):
    seat_id: int
    payment: str = Field(pattern="^(approve|decline)$")

class ReservationBatchCreate(BaseModel):
    seat_ids: list[int] = Field(min_length=1, max_length=1000)
    payment: str = Field(pattern="^(approve|decline)$")

    @field_validator("seat_ids")
    @classmethod
    def require_distinct_seats(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("não pode conter assentos repetidos")
        return value

class GeneralReservationCreate(BaseModel):
    event_id: int
    quantity: int = Field(ge=1, le=1000)
    payment: str = Field(pattern="^(approve|decline)$")

class ReservationOut(BaseModel):
    id: int
    status: str
    payment_status: str
    ticket_id: int | None = None

class TicketOut(BaseModel):
    id: int
    event_id: int
    event_title: str
    event_type: str
    seat_label: str | None
    token: str
    status: str
    share_url: str
    used_at: datetime | None

class EventAvailabilityOut(BaseModel):
    capacity: int
    available: int

class GateValidationIn(BaseModel):
    code: str
    event_id: int

class GateValidationOut(BaseModel):
    result: str
    message: str
    ticket_id: int | None = None
