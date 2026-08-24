"use client";
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import CopyTicketCodeButton from "../../components/CopyTicketCodeButton";
import { api } from "../../lib/api";
import { ticketStatusLabel } from "../../lib/ticket";

export default function Tickets() {
  const [tickets, setTickets] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [cancellingTicketId, setCancellingTicketId] = useState<number | null>(null);
  async function load() {
    try {
      setTickets(await api("/tickets"));
    } catch (e: any) {
      setError(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function cancelTicket(ticket: any) {
    const confirmed = window.confirm(
      ticket.event_type === "show"
        ? `Deseja cancelar o ingresso geral para “${ticket.event_title}”?`
        : `Deseja cancelar o ingresso para “${ticket.event_title}”, assento ${ticket.seat_label}?`,
    );
    if (!confirmed) return;

    setError("");
    setMessage("");
    setCancellingTicketId(ticket.id);
    try {
      await api(`/tickets/${ticket.id}/cancel`, { method: "POST" });
      setTickets((current) =>
        current.map((item) =>
          item.id === ticket.id ? { ...item, status: "cancelled" } : item,
        ),
      );
      setMessage(
        ticket.event_type === "show"
          ? "Ingresso cancelado. Uma unidade voltou ao estoque do show."
          : "Ingresso cancelado. O assento voltou a ficar disponível.",
      );
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCancellingTicketId(null);
    }
  }
  return (
    <>
      <div className="hero">
        <div>
          <div className="eyebrow">Minha carteira</div>
          <h1>Ingressos.</h1>
          <p className="muted">
            Cada ingresso tem um QR assinado e um link de compartilhamento.
          </p>
        </div>
      </div>
      {error && <div className="status bad ticket-feedback">{error}</div>}
      {message && <div className="status ok ticket-feedback">{message}</div>}
      <div className="grid ticket-grid">
          {tickets.map((t) => (
            <div className="card ticket" key={t.id}>
              <div>
                <span className="pill">{ticketStatusLabel(t.status)}</span>
                <h2>{t.event_title}</h2>
                <p>
                  {t.event_type === "show" ? (
                    <b>Ingresso geral</b>
                  ) : (
                    <>Assento <b>{t.seat_label}</b></>
                  )}
                </p>
                <div className="ticket-actions">
                  <a
                    href={t.share_url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn ghost"
                  >
                    Abrir link compartilhável
                  </a>
                  <CopyTicketCodeButton code={t.token} />
                  {t.status === "valid" && (
                    <button
                      type="button"
                      className="btn danger"
                      disabled={cancellingTicketId === t.id}
                      onClick={() => cancelTicket(t)}
                    >
                      {cancellingTicketId === t.id
                        ? "Cancelando…"
                        : "Cancelar ingresso"}
                    </button>
                  )}
                </div>
                <p className="mono">{t.token.slice(0, 36)}…</p>
              </div>
              <QRCodeSVG value={t.token} size={150} />
            </div>
          ))}
      </div>
    </>
  );
}
