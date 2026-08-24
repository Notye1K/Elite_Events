"use client";
import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, getUser, type SessionUser } from "../../../lib/api";
import { isEventFromPreviousDay } from "../../../lib/eventTime";

type Availability = {
  capacity: number;
  available: number;
};

const priceFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});
const MOVIE_SEATS_PER_ROW = 20;
const MOVIE_SEAT_MIN_SIZE = 28;
const MOVIE_SEAT_GAP = 6;
const MAX_TICKETS_PER_CHECKOUT = 20;

export default function EventDetail() {
  const { id } = useParams();
  const router = useRouter();
  const [event, setEvent] = useState<any>();
  const [seats, setSeats] = useState<any[]>([]);
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [ticketQuantity, setTicketQuantity] = useState(1);
  const [currentUser, setCurrentUser] = useState<SessionUser | null>(null);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [creatingCheckout, setCreatingCheckout] = useState(false);

  const load = useCallback(async () => {
    const loadedEvent = await api(`/events/${id}`);
    setEvent(loadedEvent);

    if (loadedEvent.event_type === "show") {
      const loadedAvailability = await api(`/events/${id}/availability`);
      setAvailability(loadedAvailability);
      setSeats([]);
      setSelected([]);
      setTicketQuantity((current) =>
        Math.min(
          current,
          Math.max(
            1,
            Math.min(loadedAvailability.available, MAX_TICKETS_PER_CHECKOUT),
          ),
        ),
      );
      return;
    }

    const loadedSeats = await api(`/events/${id}/seats`);
    setSeats(loadedSeats);
    setAvailability(null);
    setSelected((current) =>
      current.filter((seatId) =>
        loadedSeats.some(
          (seat: any) => seat.id === seatId && seat.status === "available",
        ),
      ),
    );
  }, [id]);

  useEffect(() => {
    function updateSession() {
      const user = getUser();
      setCurrentUser(user);
      setSessionChecked(true);
      if (user?.role !== "client") setSelected([]);
    }

    updateSession();
    window.addEventListener("auth-changed", updateSession);
    window.addEventListener("storage", updateSession);

    return () => {
      window.removeEventListener("auth-changed", updateSession);
      window.removeEventListener("storage", updateSession);
    };
  }, []);

  useEffect(() => {
    load();
    const ws = new WebSocket(
      `${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/^http/, "ws")}/ws/events/${id}/seats`,
    );
    ws.onmessage = (messageEvent) => {
      const payload = JSON.parse(messageEvent.data);
      if (typeof payload.available_count === "number") {
        setAvailability((current) =>
          current
            ? { ...current, available: payload.available_count }
            : current,
        );
        setTicketQuantity((current) =>
          Math.min(
            current,
            Math.max(
              1,
              Math.min(payload.available_count, MAX_TICKETS_PER_CHECKOUT),
            ),
          ),
        );
      }
      if (payload.seat_id) {
        setSeats((current) =>
          current.map((seat) =>
            seat.id === payload.seat_id
              ? { ...seat, status: payload.status }
              : seat,
          ),
        );
        if (payload.status !== "available") {
          setSelected((current) =>
            current.filter((seatId) => seatId !== payload.seat_id),
          );
        }
      }
    };
    return () => ws.close();
  }, [id, load]);

  const isShow = event?.event_type === "show";
  const seatMapMinWidth =
    MOVIE_SEATS_PER_ROW * MOVIE_SEAT_MIN_SIZE +
    (MOVIE_SEATS_PER_ROW - 1) * MOVIE_SEAT_GAP;
  const selectedSeatLabels = selected
    .map((seatId) => {
      const seatIndex = seats.findIndex((seat) => seat.id === seatId);
      return seatIndex >= 0
        ? `${seatIndex + 1} (${seats[seatIndex].label})`
        : null;
    })
    .filter(Boolean)
    .join(", ");
  const eventFromPreviousDay = Boolean(
    event && isEventFromPreviousDay(event.starts_at),
  );

  if (!event) return <div className="card">Carregando…</div>;

  function toggleSeat(seatId: number) {
    if (
      isShow ||
      currentUser?.role !== "client" ||
      eventFromPreviousDay
    ) {
      return;
    }
    setSelected((current) =>
      current.includes(seatId)
        ? current.filter((selectedId) => selectedId !== seatId)
        : [...current, seatId],
    );
    setError("");
  }

  function cancelSelection() {
    if (selected.length === 0) return;
    setSelected([]);
    setError("");
  }

  async function reserve() {
    const user = getUser();
    if (!user) {
      router.push("/login");
      return;
    }
    if (user.role !== "client") {
      setError("Somente clientes podem comprar ingressos.");
      return;
    }
    if (eventFromPreviousDay) {
      setError(
        "Não é possível reservar ingressos para eventos de dias anteriores.",
      );
      return;
    }
    if (isShow && (!availability || availability.available === 0)) {
      setError("Os ingressos deste show estão esgotados.");
      return;
    }
    if (!isShow && selected.length === 0) {
      setError("Escolha pelo menos um assento.");
      return;
    }

    setError("");
    setCreatingCheckout(true);
    try {
      const checkout = await api("/checkout/sessions", {
        method: "POST",
        body: JSON.stringify(
          isShow
            ? { event_id: Number(id), quantity: ticketQuantity }
            : { event_id: Number(id), seat_ids: selected },
        ),
      });
      setSelected([]);
      setTicketQuantity(1);
      router.push(`/checkout/${checkout.id}`);
    } catch (caughtError: any) {
      setError(caughtError.message);
      load();
    } finally {
      setCreatingCheckout(false);
    }
  }

  return (
    <div className="event-detail-page">
      {event.image_url && (
        <div className="event-detail-background" aria-hidden="true">
          <Image
            src={event.image_url}
            alt=""
            fill
            sizes="100vw"
            className="event-detail-background-image"
          />
        </div>
      )}
      <div className="event-detail-content">
        <div className="hero">
          <div>
            <div className="eyebrow">{isShow ? "Show" : "Filme"}</div>
            <h1>{event.title}</h1>
            <p className="muted">
              {event.location} · {new Date(event.starts_at).toLocaleString("pt-BR")}
            </p>
          </div>
          <div className="card">
            {event.image_url && (
              <Image
                src={event.image_url}
                alt={`Imagem de ${event.title}`}
                width={500}
                height={750}
                className="event-detail-image"
              />
            )}
            <div className="price">
              {priceFormatter.format(event.price_cents / 100)}
            </div>
            <p className="muted">por ingresso</p>
          </div>
        </div>

        <div className="card seat-map-card">
          {isShow ? (
            <div className="show-ticket-counter" aria-live="polite">
              <div className="eyebrow">Ingressos disponíveis</div>
              <div className="show-ticket-availability">
                {availability?.available ?? "…"}
              </div>
              <p className="muted">
                de {availability?.capacity ?? event.capacity} ingressos
              </p>
              {availability?.available === 0 && (
                <div className="status bad">Show esgotado</div>
              )}
            </div>
          ) : (
            <div className="seat-map-viewport">
              <div
                className="seat-map-stage"
                style={{
                  width: "min(100%, 900px)",
                  minWidth: `${seatMapMinWidth}px`,
                }}
              >
                <div className="screen">TELA</div>
                <div
                  className="seatmap"
                  style={{
                    gridTemplateColumns: `repeat(${MOVIE_SEATS_PER_ROW}, minmax(${MOVIE_SEAT_MIN_SIZE}px, 1fr))`,
                  }}
                >
                  {seats.map((seat: any, index) => (
                    <button
                      key={seat.id}
                      disabled={
                        seat.status !== "available" ||
                        currentUser?.role !== "client" ||
                        eventFromPreviousDay
                      }
                      onClick={() => toggleSeat(seat.id)}
                      className={`seat ${seat.status !== "available" ? "taken" : ""} ${currentUser?.role !== "client" || eventFromPreviousDay ? "view-only" : ""} ${selected.includes(seat.id) ? "selected" : ""}`}
                      title={
                        eventFromPreviousDay
                          ? `Lugar ${index + 1} (${seat.label}) — reservas encerradas para este evento`
                          : currentUser?.role === "client"
                            ? `Lugar ${index + 1} (${seat.label})`
                            : `Lugar ${index + 1} (${seat.label}) — compra exclusiva para clientes`
                      }
                      aria-label={`Lugar ${index + 1}, assento ${seat.label}`}
                      aria-pressed={selected.includes(seat.id)}
                    >
                      {index + 1}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {!sessionChecked ? (
            <p className="muted purchase-restriction">Verificando sessão…</p>
          ) : eventFromPreviousDay ? (
            <div className="purchase-restriction">
              <p className="muted">
                As reservas estão encerradas porque este evento ocorreu em um dia anterior.
              </p>
            </div>
          ) : currentUser?.role === "client" ? (
            isShow ? (
              <div className="show-purchase-controls">
                <div>
                  <span className="muted">Quantidade</span>
                  <div className="show-ticket-quantity">
                    <button
                      type="button"
                      className="btn ghost"
                      onClick={() =>
                        setTicketQuantity((current) => Math.max(1, current - 1))
                      }
                      disabled={ticketQuantity <= 1}
                      aria-label="Diminuir quantidade"
                    >
                      −
                    </button>
                    <b>{ticketQuantity}</b>
                    <button
                      type="button"
                      className="btn ghost"
                      onClick={() =>
                        setTicketQuantity((current) =>
                          Math.min(
                            availability?.available ?? 1,
                            MAX_TICKETS_PER_CHECKOUT,
                            current + 1,
                          ),
                        )
                      }
                      disabled={
                        !availability ||
                        availability.available === 0 ||
                        ticketQuantity >= availability.available ||
                        ticketQuantity >= MAX_TICKETS_PER_CHECKOUT
                      }
                      aria-label="Aumentar quantidade"
                    >
                      +
                    </button>
                  </div>
                </div>
                <button
                  className="btn primary"
                  onClick={reserve}
                  disabled={
                    creatingCheckout ||
                    !availability ||
                    availability.available === 0
                  }
                >
                  {creatingCheckout
                    ? "Preparando pagamento…"
                    : "Continuar para pagamento"}
                </button>
              </div>
            ) : (
              <div className="row" style={{ marginTop: 20 }}>
                <div>
                  {selected.length > 0 ? (
                    <div className="seat-selection-summary">
                      <b>
                        {selected.length}{" "}
                        {selected.length === 1
                          ? "assento selecionado"
                          : "assentos selecionados"}
                      </b>
                      <span className="muted" title={selectedSeatLabels}>
                        Lugares: {selectedSeatLabels}
                      </span>
                    </div>
                  ) : (
                    <span className="muted">Selecione um ou mais lugares</span>
                  )}
                </div>
                <div className="row">
                  <button
                    className="btn primary"
                    onClick={reserve}
                    disabled={creatingCheckout || selected.length === 0}
                  >
                    {creatingCheckout
                      ? "Preparando pagamento…"
                      : "Continuar para pagamento"}
                  </button>
                  <button
                    className="btn ghost"
                    onClick={cancelSelection}
                    disabled={selected.length === 0}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )
          ) : (
            <div className="purchase-restriction">
              <p className="muted">
                {currentUser
                  ? "A compra de ingressos é exclusiva para usuários com perfil de cliente."
                  : "Entre com um perfil de cliente para comprar ingressos."}
              </p>
              {!currentUser && (
                <Link className="btn primary" href="/login">
                  Entrar como cliente
                </Link>
              )}
            </div>
          )}

          {error && (
            <div className="status bad" style={{ marginTop: 16 }}>
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
