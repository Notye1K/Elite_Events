"use client";
import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, getUser, type SessionUser } from "../../../lib/api";
import { isEventFromPreviousDay } from "../../../lib/eventTime";

export default function EventDetail() {
  const { id } = useParams();
  const router = useRouter();
  const [event, setEvent] = useState<any>();
  const [seats, setSeats] = useState<any[]>([]);
  const [currentUser, setCurrentUser] = useState<SessionUser | null>(null);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [selected, setSelected] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function load() {
    setEvent(await api(`/events/${id}`));
    const loadedSeats = await api(`/events/${id}/seats`);
    setSeats(loadedSeats);
    setSelected((current) =>
      current.filter((seatId) =>
        loadedSeats.some(
          (seat: any) => seat.id === seatId && seat.status === "available",
        ),
      ),
    );
  }
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
    ws.onmessage = (m) => {
      const p = JSON.parse(m.data);
      if (p.seat_id) {
        setSeats((s) =>
          s.map((x) => (x.id === p.seat_id ? { ...x, status: p.status } : x)),
        );
        if (p.status !== "available") {
          setSelected((current) =>
            current.filter((seatId) => seatId !== p.seat_id),
          );
        }
      }
    };
    return () => ws.close();
  }, [id]);
  const seatsPerVisualRow = Math.max(1, Math.min(seats.length, 40));
  const seatMapWidth = Math.max(
    seatsPerVisualRow * 22 + (seatsPerVisualRow - 1) * 4,
    280,
  );
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
    if (currentUser?.role !== "client" || eventFromPreviousDay) return;
    setSelected((current) =>
      current.includes(seatId)
        ? current.filter((selectedId) => selectedId !== seatId)
        : [...current, seatId],
    );
    setError("");
    setMessage("");
  }
  async function reserve(payment: string) {
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
      setError("Não é possível reservar ingressos para eventos de dias anteriores.");
      return;
    }
    if (selected.length === 0) {
      setError("Escolha pelo menos um assento.");
      return;
    }
    setError("");
    setMessage("");
    try {
      const reservations = await api("/reservations/batch", {
        method: "POST",
        body: JSON.stringify({ seat_ids: selected, payment }),
      });
      if (reservations.every((reservation: any) => reservation.status === "cancelled")) {
        setError("Pagamento recusado. Os lugares voltaram ao estoque.");
        return;
      }
      setMessage(
        `Pagamento aprovado. ${reservations.length} ${reservations.length === 1 ? "ingresso criado" : "ingressos criados"}.`,
      );
      setSelected([]);
      setTimeout(() => router.push("/tickets"), 600);
    } catch (e: any) {
      setError(e.message);
      load();
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
          <div className="eyebrow">Evento</div>
          <h1>{event.title}</h1>
          <p className="muted">
            {event.location} ·{" "}
            {new Date(event.starts_at).toLocaleString("pt-BR")}
          </p>
        </div>
        <div className="card">
          {event.image_url && (
            <Image
              src={event.image_url}
              alt={`Pôster de ${event.title}`}
              width={500}
              height={750}
              className="event-detail-image"
            />
          )}
          <div className="price">R$ {(event.price_cents / 100).toFixed(2)}</div>
          <p className="muted">por assento</p>
        </div>
      </div>
      <div className="card seat-map-card">
        <div className="seat-map-viewport">
          <div
            className="seat-map-stage"
            style={{
              width: `min(100%, ${seatMapWidth}px)`,
              minWidth: `${seatMapWidth}px`,
            }}
          >
            <div className="screen">TELA / PALCO</div>
            <div
              className="seatmap"
              style={{
                gridTemplateColumns: `repeat(${seatsPerVisualRow}, minmax(22px, 1fr))`,
              }}
            >
              {seats.map((s: any, index) => (
                <button
                  key={s.id}
                  disabled={
                    s.status !== "available" ||
                    currentUser?.role !== "client" ||
                    eventFromPreviousDay
                  }
                  onClick={() => toggleSeat(s.id)}
                  className={`seat ${s.status !== "available" ? "taken" : ""} ${currentUser?.role !== "client" || eventFromPreviousDay ? "view-only" : ""} ${selected.includes(s.id) ? "selected" : ""}`}
                  title={
                    eventFromPreviousDay
                      ? `Lugar ${index + 1} (${s.label}) — reservas encerradas para este evento`
                      : currentUser?.role === "client"
                      ? `Lugar ${index + 1} (${s.label})`
                      : `Lugar ${index + 1} (${s.label}) — compra exclusiva para clientes`
                  }
                  aria-label={`Lugar ${index + 1}, assento ${s.label}`}
                  aria-pressed={selected.includes(s.id)}
                >
                  {index + 1}
                </button>
              ))}
            </div>
          </div>
        </div>
        {!sessionChecked ? (
          <p className="muted purchase-restriction">Verificando sessão…</p>
        ) : eventFromPreviousDay ? (
          <div className="purchase-restriction">
            <p className="muted">
              As reservas estão encerradas porque este evento ocorreu em um dia anterior.
            </p>
          </div>
        ) : currentUser?.role === "client" ? (
          <div className="row" style={{ marginTop: 20 }}>
            <div>
              {selected.length > 0 ? (
                <div className="seat-selection-summary">
                  <b>
                    {selected.length} {selected.length === 1 ? "assento selecionado" : "assentos selecionados"}
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
              <button className="btn primary" onClick={() => reserve("approve")}>
                Pagar simulado
              </button>
              <button className="btn ghost" onClick={() => reserve("decline")}>
                Simular recusa
              </button>
            </div>
          </div>
        ) : (
          <div className="purchase-restriction">
            <p className="muted">
              {currentUser
                ? "A compra de ingressos é exclusiva para usuários com perfil de cliente."
                : "Entre com um perfil de cliente para selecionar e comprar ingressos."}
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
        {message && (
          <div className="status ok" style={{ marginTop: 16 }}>
            {message}
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
