"use client";
import { useEffect, useState } from "react";
import Image from "next/image";
import { useParams, useRouter } from "next/navigation";
import { api, getUser } from "../../../lib/api";

export default function EventDetail() {
  const { id } = useParams();
  const router = useRouter();
  const [event, setEvent] = useState<any>();
  const [seats, setSeats] = useState<any[]>([]);
  const [selected, setSelected] = useState<number>();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function load() {
    setEvent(await api(`/events/${id}`));
    setSeats(await api(`/events/${id}/seats`));
  }
  useEffect(() => {
    load();
    const ws = new WebSocket(
      `${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/^http/, "ws")}/ws/events/${id}/seats`,
    );
    ws.onmessage = (m) => {
      const p = JSON.parse(m.data);
      if (p.seat_id)
        setSeats((s) =>
          s.map((x) => (x.id === p.seat_id ? { ...x, status: p.status } : x)),
        );
    };
    return () => ws.close();
  }, [id]);
  const seatsPerVisualRow = Math.max(1, Math.min(seats.length, 40));
  const seatMapWidth = Math.max(
    seatsPerVisualRow * 22 + (seatsPerVisualRow - 1) * 4,
    280,
  );
  const selectedSeatIndex = seats.findIndex((seat) => seat.id === selected);
  if (!event) return <div className="card">Carregando…</div>;
  async function reserve(payment: string) {
    if (!getUser()) {
      router.push("/login");
      return;
    }
    if (!selected) {
      setError("Escolha um assento.");
      return;
    }
    setError("");
    setMessage("");
    try {
      const r = await api("/reservations", {
        method: "POST",
        body: JSON.stringify({ seat_id: selected, payment }),
      });
      if (r.status === "cancelled") {
        setError("Pagamento recusado. O lugar voltou ao estoque.");
        return;
      }
      setMessage("Pagamento aprovado. Ingresso criado.");
      setTimeout(() => router.push("/tickets"), 600);
    } catch (e: any) {
      setError(e.message);
      load();
    }
  }
  return (
    <>
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
                  disabled={s.status !== "available"}
                  onClick={() => setSelected(s.id)}
                  className={`seat ${s.status !== "available" ? "taken" : ""} ${selected === s.id ? "selected" : ""}`}
                  title={`Lugar ${index + 1} (${s.label})`}
                  aria-label={`Lugar ${index + 1}, assento ${s.label}`}
                >
                  {index + 1}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="row" style={{ marginTop: 20 }}>
          <div>
            {selected ? (
              <b>
                Selecionado: lugar {selectedSeatIndex + 1} ({seats[selectedSeatIndex]?.label})
              </b>
            ) : (
              <span className="muted">Selecione um lugar</span>
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
    </>
  );
}
