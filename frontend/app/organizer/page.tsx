"use client";
import Image from "next/image";
import { useEffect, useState } from "react";
import { api, ApiError, getErrorMessage } from "../../lib/api";

const HOUR_IN_MS = 60 * 60 * 1000;
const DAY_IN_MS = 24 * HOUR_IN_MS;
const MAX_EVENT_ADVANCE_DAYS = 3650;
const MAX_EVENT_PRICE_CENTS = 10_000_000;
const priceFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

function toDateTimeLocal(date: Date) {
  const localTime = date.getTime() - date.getTimezoneOffset() * 60_000;
  return new Date(localTime).toISOString().slice(0, 16);
}

function isValidImageUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export default function Organizer() {
  const [events, setEvents] = useState<any[]>([]);
  const [tmdbCatalog, setTmdbCatalog] = useState<any[]>([]);
  const [ticketmasterCatalog, setTicketmasterCatalog] = useState<any[]>([]);
  const [form, setForm] = useState({
    title: "",
    description: "",
    image_url: "",
    event_type: "movie",
    starts_at: "",
    location: "",
    capacity: "200",
    price_cents: "",
    published: true,
    external_source: "tmdb",
    external_id: "",
  });
  const [tmdbQuery, setTmdbQuery] = useState("");
  const [tmdbStatus, setTmdbStatus] = useState<
    "idle" | "loading" | "success" | "empty"
  >("idle");
  const [lastTmdbQuery, setLastTmdbQuery] = useState("");
  const [ticketmasterQuery, setTicketmasterQuery] = useState("");
  const [ticketmasterStatus, setTicketmasterStatus] = useState<
    "idle" | "loading" | "success" | "empty"
  >("idle");
  const [lastTicketmasterQuery, setLastTicketmasterQuery] = useState("");
  const [error, setError] = useState("");
  const [deletingEventId, setDeletingEventId] = useState<number | null>(null);
  const minimumEventDate = new Date(Date.now() + 24 * HOUR_IN_MS);
  minimumEventDate.setSeconds(0, 0);
  minimumEventDate.setMinutes(minimumEventDate.getMinutes() + 1);
  const minimumStartsAt = toDateTimeLocal(minimumEventDate);
  const maximumStartsAt = toDateTimeLocal(
    new Date(Date.now() + MAX_EVENT_ADVANCE_DAYS * DAY_IN_MS),
  );
  async function load() {
    try {
      setEvents(await api("/organizer/events"));
    } catch (error) {
      setError(getErrorMessage(error));
    }
  }
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    if (!error) return;

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setError("");
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [error]);
  async function searchTmdb() {
    if (tmdbStatus === "loading") return;

    const query = tmdbQuery.trim();
    if (!query) {
      setTmdbCatalog([]);
      setLastTmdbQuery("");
      setTmdbStatus("empty");
      return;
    }

    setError("");
    setTmdbCatalog([]);
    setTmdbStatus("loading");
    setLastTmdbQuery(query);
    try {
      const r = await api(
        `/external/catalog?source=tmdb&q=${encodeURIComponent(query)}`,
      );
      if (!r.configured) {
        throw new ApiError("A integração com o TMDb não está configurada.");
      }
      setTmdbCatalog(r.items);
      setTmdbStatus(r.items.length > 0 ? "success" : "empty");
    } catch (error) {
      setTmdbCatalog([]);
      setTmdbStatus("idle");
      setError(getErrorMessage(error));
    }
  }
  async function searchTicketmaster() {
    if (ticketmasterStatus === "loading") return;

    const query = ticketmasterQuery.trim();
    if (!query) {
      setTicketmasterCatalog([]);
      setLastTicketmasterQuery("");
      setTicketmasterStatus("empty");
      return;
    }

    setError("");
    setTicketmasterCatalog([]);
    setTicketmasterStatus("loading");
    setLastTicketmasterQuery(query);
    try {
      const r = await api(
        `/external/catalog?source=ticketmaster&q=${encodeURIComponent(query)}`,
      );
      if (!r.configured) {
        throw new ApiError(
          "A integração com a Ticketmaster não está configurada.",
        );
      }
      setTicketmasterCatalog(r.items);
      setTicketmasterStatus(r.items.length > 0 ? "success" : "empty");
    } catch (error) {
      setTicketmasterCatalog([]);
      setTicketmasterStatus("idle");
      setError(getErrorMessage(error));
    }
  }
  async function create(e: any) {
    e.preventDefault();
    setError("");
    try {
      await api("/organizer/events", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          starts_at: new Date(form.starts_at).toISOString(),
          capacity: Number(form.capacity),
          price_cents: Number(form.price_cents),
          image_url: form.image_url.trim() || null,
          external_source: form.external_id ? form.external_source : null,
        }),
      });
      setForm({
        title: "",
        description: "",
        image_url: "",
        event_type: "movie",
        starts_at: "",
        location: "",
        capacity: "200",
        price_cents: "",
        published: true,
        external_source: "tmdb",
        external_id: "",
      });
      setTmdbCatalog([]);
      setTmdbQuery("");
      setTmdbStatus("idle");
      setLastTmdbQuery("");
      setTicketmasterCatalog([]);
      setTicketmasterQuery("");
      setTicketmasterStatus("idle");
      setLastTicketmasterQuery("");
      load();
    } catch (error) {
      setError(getErrorMessage(error));
    }
  }
  async function removeEvent(event: any) {
    const confirmed = window.confirm(
      `Deseja realmente excluir o evento “${event.title}”?`,
    );
    if (!confirmed) return;

    setError("");
    setDeletingEventId(event.id);
    try {
      await api(`/organizer/events/${event.id}`, { method: "DELETE" });
      setEvents((current) => current.filter((item) => item.id !== event.id));
    } catch (error) {
      setError(getErrorMessage(error));
    } finally {
      setDeletingEventId(null);
    }
  }
  return (
    <>
      {error && (
        <div
          className="error-popup-backdrop"
          onMouseDown={() => setError("")}
        >
          <section
            className="error-popup"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="error-popup-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="error-popup-icon" aria-hidden="true">
              !
            </div>
            <div>
              <h2 id="error-popup-title">Não foi possível concluir</h2>
              <p>{error}</p>
            </div>
            <button
              type="button"
              className="btn primary"
              onClick={() => setError("")}
              autoFocus
            >
              Entendi
            </button>
          </section>
        </div>
      )}
      <div className="hero">
        <div>
          <div className="eyebrow">Back office</div>
          <h1>Organizador.</h1>
          <p className="muted">
            Catálogo externo + publicação + gestão de capacidade.
          </p>
        </div>
        <div className="card">
          <div className="big-stat">{events.length}</div>
          <p className="muted">eventos próprios</p>
        </div>
      </div>
      <div className="grid">
        <div className="organizer-catalog-column">
          <div className="card">
            <h2>Encontre um filme do TMDb</h2>
            <div className="row">
              <input
                value={tmdbQuery}
                placeholder="Digite o nome do filme"
                onChange={(e) => setTmdbQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && searchTmdb()}
                maxLength={200}
              />
              <button
                className="btn ghost"
                onClick={searchTmdb}
                disabled={tmdbStatus === "loading"}
              >
                {tmdbStatus === "loading" ? "Buscando…" : "Buscar"}
              </button>
            </div>
            <div className="catalog-feedback" aria-live="polite">
              {tmdbStatus === "loading" && (
                <span role="status">
                  <span className="catalog-spinner" aria-hidden="true" />
                  Buscando filmes no TMDb…
                </span>
              )}
              {tmdbStatus === "empty" && (
                <span role="status">
                  {lastTmdbQuery
                    ? `Nenhum filme encontrado para “${lastTmdbQuery}”.`
                    : "Digite o nome de um filme para pesquisar."}
                </span>
              )}
            </div>
            <div className="catalog-results">
              {tmdbCatalog.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className="catalog-movie"
                  onClick={() =>
                    setForm((f) => ({
                      ...f,
                      title: c.title,
                      description: c.overview || "",
                      image_url: c.image || "",
                      event_type: "movie",
                      capacity: "200",
                      external_source: "tmdb",
                      external_id: c.id,
                    }))
                  }
                >
                  {c.image ? (
                    <Image
                      src={c.image}
                      alt={`Pôster de ${c.title}`}
                      width={72}
                      height={108}
                      className="catalog-movie-image"
                    />
                  ) : (
                    <span className="catalog-movie-placeholder">Sem imagem</span>
                  )}
                  <span className="catalog-movie-info">
                    <strong>{c.title}</strong>
                    {c.date && <small>{c.date.slice(0, 4)}</small>}
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className="card">
            <h2>Encontre um show na Ticketmaster</h2>
            <div className="row">
              <input
                value={ticketmasterQuery}
                placeholder="Digite o nome do artista ou show"
                onChange={(e) => setTicketmasterQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && searchTicketmaster()}
                maxLength={200}
              />
              <button
                className="btn ghost"
                onClick={searchTicketmaster}
                disabled={ticketmasterStatus === "loading"}
              >
                {ticketmasterStatus === "loading" ? "Buscando…" : "Buscar"}
              </button>
            </div>
            <div className="catalog-feedback" aria-live="polite">
              {ticketmasterStatus === "loading" && (
                <span role="status">
                  <span className="catalog-spinner" aria-hidden="true" />
                  Buscando shows na Ticketmaster…
                </span>
              )}
              {ticketmasterStatus === "empty" && (
                <span role="status">
                  {lastTicketmasterQuery
                    ? `Nenhum show encontrado para “${lastTicketmasterQuery}”.`
                    : "Digite o nome de um artista ou show para pesquisar."}
                </span>
              )}
            </div>
            <div className="catalog-results">
              {ticketmasterCatalog.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className="catalog-movie"
                  onClick={() =>
                    setForm((f) => ({
                      ...f,
                      title: c.title,
                      description: c.overview || "",
                      image_url: c.image || "",
                      event_type: "show",
                      starts_at: c.starts_at
                        ? toDateTimeLocal(new Date(c.starts_at))
                        : f.starts_at,
                      location: c.location || f.location,
                      capacity: f.event_type === "show" ? f.capacity : "",
                      external_source: "ticketmaster",
                      external_id: c.id,
                    }))
                  }
                >
                  {c.image ? (
                    <Image
                      src={c.image}
                      alt={`Imagem de ${c.title}`}
                      width={72}
                      height={108}
                      className="catalog-movie-image"
                    />
                  ) : (
                    <span className="catalog-movie-placeholder">Sem imagem</span>
                  )}
                  <span className="catalog-movie-info">
                    <strong>{c.title}</strong>
                    {c.date && <small>{c.date}</small>}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="card">
          <h2>Novo evento</h2>
          <form className="form" onSubmit={create}>
            <label>
              Tipo de evento
              <select
                value={form.event_type}
                onChange={(e) => {
                  const eventType = e.target.value;
                  setForm({
                    ...form,
                    event_type: eventType,
                    capacity: eventType === "movie" ? "200" : "",
                    external_source:
                      eventType === "movie" ? "tmdb" : "ticketmaster",
                    external_id: "",
                  });
                }}
              >
                <option value="movie">Filme</option>
                <option value="show">Show</option>
              </select>
            </label>
            {isValidImageUrl(form.image_url) && (
              <Image
                src={form.image_url}
                alt={`Pôster selecionado para ${form.title}`}
                width={500}
                height={750}
                className="selected-event-image"
              />
            )}
            <label>
              Título
              <input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                maxLength={255}
                required
              />
            </label>
            <label>
              Descrição
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
                maxLength={5000}
                required
              />
            </label>
            <label>
              Imagem (URL)
              <input
                type="url"
                value={form.image_url}
                placeholder="https://exemplo.com/imagem.jpg"
                onChange={(e) =>
                  setForm({ ...form, image_url: e.target.value })
                }
                maxLength={500}
              />
              <span className="muted">Opcional. Use uma URL HTTP ou HTTPS.</span>
            </label>
            <label>
              Data/hora
              <input
                type="datetime-local"
                value={form.starts_at}
                onChange={(e) =>
                  setForm({
                    ...form,
                    starts_at: e.target.value,
                  })
                }
                min={minimumStartsAt}
                max={maximumStartsAt}
                required
              />
            </label>
            <label>
              Local
              <input
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
                maxLength={255}
                required
              />
            </label>
            <div className="grid">
              <label>
                Capacidade
                <input
                  type="number"
                  value={form.capacity}
                  onChange={(e) =>
                    setForm({ ...form, capacity: e.target.value })
                  }
                  min="1"
                  max="1000"
                  step="1"
                  disabled={form.event_type === "movie"}
                  required
                />
                <span className="muted">
                  {form.event_type === "movie"
                    ? "Filmes usam 200 cadeiras fixas, em fileiras de 20."
                    : "Informe a quantidade total de ingressos do show."}
                </span>
              </label>
              <label>
                Preço (centavos)
                <input
                  type="number"
                  value={form.price_cents}
                  onChange={(e) =>
                    setForm({ ...form, price_cents: e.target.value })
                  }
                  min="0"
                  max={MAX_EVENT_PRICE_CENTS}
                  step="1"
                  required
                />
              </label>
            </div>
            <label>
              ID externo
              <input
                value={form.external_id}
                onChange={(e) =>
                  setForm({ ...form, external_id: e.target.value })
                }
                maxLength={120}
              />
            </label>
            <button className="btn accent">Publicar evento</button>
          </form>
        </div>
      </div>
      <div style={{ marginTop: 18 }} className="grid organizer-event-grid">
        {events.map((e) => (
          <div className="card organizer-event-card" key={e.id}>
            <div className="organizer-event-media">
              {e.image_url && (
                <Image
                  src={e.image_url}
                  alt={`Pôster de ${e.title}`}
                  width={500}
                  height={750}
                  className="event-card-image organizer-event-image"
                />
              )}
            </div>
            <div className="organizer-event-content">
              <h3 className="card-text-single" title={e.title}>
                {e.title}
              </h3>
              <p
                className="muted organizer-event-date"
                title={new Date(e.starts_at).toLocaleString("pt-BR", {
                  dateStyle: "short",
                  timeStyle: "short",
                })}
              >
                {new Date(e.starts_at).toLocaleString("pt-BR", {
                  dateStyle: "short",
                  timeStyle: "short",
                })}
              </p>
              <div className="organizer-event-meta">
                <p className="muted card-text-single" title={e.location}>
                  {e.location}
                </p>
                <span title={priceFormatter.format(e.price_cents / 100)}>
                  {priceFormatter.format(e.price_cents / 100)}
                </span>
              </div>
              <button
                type="button"
                className="btn danger organizer-delete-button"
                onClick={() => removeEvent(e)}
                disabled={deletingEventId === e.id}
              >
                {deletingEventId === e.id ? "Excluindo…" : "Excluir evento"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
