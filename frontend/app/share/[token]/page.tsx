"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import CopyTicketCodeButton from "../../../components/CopyTicketCodeButton";
import { api } from "../../../lib/api";
import { ticketStatusLabel } from "../../../lib/ticket";

export default function Share() {
  const { token } = useParams();
  const [ticket, setTicket] = useState<any>();
  const [error, setError] = useState("");
  useEffect(() => {
    api(`/share/${token}`)
      .then(setTicket)
      .catch((e) => setError(e.message));
  }, [token]);
  if (error) return <div className="status bad">{error}</div>;
  if (!ticket) return <div className="card">Carregando ingresso…</div>;
  return (
    <div className="card" style={{ maxWidth: 760, margin: "40px auto" }}>
      <div className="ticket">
        <div>
          <div className="eyebrow">Ingresso compartilhado</div>
          <h1>{ticket.event_title}</h1>
          <p>
            Assento <b>{ticket.seat_label}</b>
          </p>
          <span className="pill">{ticketStatusLabel(ticket.status)}</span>
          <div className="ticket-actions">
            <CopyTicketCodeButton code={ticket.token} />
          </div>
        </div>
        <QRCodeSVG value={ticket.token} size={180} />
      </div>
      <p className="footer-note">
        O QR é um token assinado pelo servidor e validado contra o ingresso
        persistido.
      </p>
    </div>
  );
}
