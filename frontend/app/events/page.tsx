"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { api } from "../../lib/api";

const priceFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

export default function Events() {
  const [events, setEvents] = useState<any[]>([]);
  const [q, setQ] = useState("");
  async function load() {
    setEvents(await api(`/events${q ? `?q=${encodeURIComponent(q)}` : ""}`));
  }
  useEffect(() => {
    load();
  }, []);
  return (
    <>
      <div className="hero">
        <div>
          <div className="eyebrow">Agenda</div>
          <h1>Eventos publicados.</h1>
          <p className="muted">
            Busque por nome ou local. Os dados editoriais são enriquecidos a
            partir do catálogo externo, mas o organizador controla o evento
            publicado.
          </p>
        </div>
      </div>
      <div className="search">
        <input
          placeholder="Buscar evento ou local"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
        />
        <button className="btn primary" onClick={load}>
          Buscar
        </button>
      </div>
      <div className="grid event-grid">
        {events.map((e) => (
          <Link
            className="card event-card"
            href={`/events/${e.id}`}
            key={e.id}
            style={{ textDecoration: "none", color: "inherit" }}
          >
            {e.image_url && (
              <Image
                src={e.image_url}
                alt={`Pôster de ${e.title}`}
                width={500}
                height={750}
                className="event-card-image"
              />
            )}
            <div className="row">
              <span
                className="pill card-text-single"
                title={new Date(e.starts_at).toLocaleDateString("pt-BR")}
              >
                {new Date(e.starts_at).toLocaleDateString("pt-BR")}
              </span>
              <span
                className="price card-text-single"
                title={priceFormatter.format(e.price_cents / 100)}
              >
                {priceFormatter.format(e.price_cents / 100)}
              </span>
            </div>
            <h3 className="card-text-single" title={e.title}>
              {e.title}
            </h3>
            <p className="muted card-text-single" title={e.location}>
              {e.location}
            </p>
            <p className="muted card-text-multiline" title={e.description}>
              {e.description}
            </p>
          </Link>
        ))}
      </div>
    </>
  );
}
