from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

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
    title: str
    description: str = ""
    image_url: str | None = None
    event_type: str = "seated"
    starts_at: datetime
    location: str
    capacity: int = Field(gt=0, le=1000)
    price_cents: int = Field(ge=0)
    published: bool = False
    external_source: str | None = None
    external_id: str | None = None

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

class ReservationOut(BaseModel):
    id: int
    status: str
    payment_status: str
    ticket_id: int | None = None

class TicketOut(BaseModel):
    id: int
    event_id: int
    event_title: str
    seat_label: str
    token: str
    status: str
    share_url: str
    used_at: datetime | None

class GateValidationIn(BaseModel):
    code: str
    event_id: int

class GateValidationOut(BaseModel):
    result: str
    message: str
    ticket_id: int | None = None
