"use client";
import Image from "next/image";
import { useEffect, useState } from "react";
import { api, ApiError, getErrorMessage } from "../../lib/api";

const HOUR_IN_MS = 60 * 60 * 1000;
const DAY_IN_MS = 24 * HOUR_IN_MS;
const MAX_EVENT_ADVANCE_DAYS = 3650;
const MAX_EVENT_PRICE_CENTS = 10_000_000;

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
  const [catalog, setCatalog] = useState<any[]>([]);
  const [form, setForm] = useState({
    title: "",
    description: "",
    image_url: "",
    event_type: "seated",
    starts_at: "",
    location: "",
    capacity: "",
    price_cents: "",
    published: true,
    external_source: "tmdb",
    external_id: "",
  });
  const [q, setQ] = useState("");
  const [catalogStatus, setCatalogStatus] = useState<
    "idle" | "loading" | "success" | "empty"
  >("idle");
  const [lastCatalogQuery, setLastCatalogQuery] = useState("");
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
  async function search() {
    if (catalogStatus === "loading") return;

    const query = q.trim();
    if (!query) {
      setCatalog([]);
      setLastCatalogQuery("");
      setCatalogStatus("empty");
      return;
    }

    setError("");
    setCatalog([]);
    setCatalogStatus("loading");
    setLastCatalogQuery(query);
    try {
      const r = await api(
        `/external/catalog?source=tmdb&q=${encodeURIComponent(query)}`,
      );
      if (!r.configured) {
        throw new ApiError("A integração com o TMDb não está configurada.");
      }
      setCatalog(r.items);
      setCatalogStatus(r.items.length > 0 ? "success" : "empty");
    } catch (error) {
      setCatalog([]);
      setCatalogStatus("idle");
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
        }),
      });
      setForm({
        ...form,
        title: "",
        description: "",
        image_url: "",
        starts_at: "",
        location: "",
        capacity: "",
        price_cents: "",
        external_id: "",
      });
      setCatalog([]);
      setQ("");
      setCatalogStatus("idle");
      setLastCatalogQuery("");
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
        <div className="card">
          <h2>Encontre um filme do TMDb</h2>
          <div className="row">
            <input
              value={q}
              placeholder="Digite o nome do filme"
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
              maxLength={200}
            />
            <button
              className="btn ghost"
              onClick={search}
              disabled={catalogStatus === "loading"}
            >
              {catalogStatus === "loading" ? "Buscando…" : "Buscar"}
            </button>
          </div>
          <div className="catalog-feedback" aria-live="polite">
            {catalogStatus === "loading" && (
              <span role="status">
                <span className="catalog-spinner" aria-hidden="true" />
                Buscando filmes no TMDb…
              </span>
            )}
            {catalogStatus === "empty" && (
              <span role="status">
                {lastCatalogQuery
                  ? `Nenhum filme encontrado para “${lastCatalogQuery}”.`
                  : "Digite o nome de um filme para pesquisar."}
              </span>
            )}
          </div>
          <div className="catalog-results">
            {catalog.map((c) => (
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
          <h2>Novo evento</h2>
          <form className="form" onSubmit={create}>
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
                  required
                />
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
      <div style={{ marginTop: 18 }} className="grid">
        {events.map((e) => (
          <div className="card organizer-event-card" key={e.id}>
            {e.image_url && (
              <Image
                src={e.image_url}
                alt={`Pôster de ${e.title}`}
                width={500}
                height={750}
                className="event-card-image organizer-event-image"
              />
            )}
            <h3 className="card-text-single" title={e.title}>
              {e.title}
            </h3>
            <p
              className="muted card-text-single"
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
            <p
              className="muted card-text-single"
              title={`${e.location} · R$ ${(e.price_cents / 100).toFixed(2)}`}
            >
              {e.location} · R$ {(e.price_cents / 100).toFixed(2)}
            </p>
            <button
              type="button"
              className="btn danger organizer-delete-button"
              onClick={() => removeEvent(e)}
              disabled={deletingEventId === e.id}
            >
              {deletingEventId === e.id ? "Excluindo…" : "Excluir evento"}
            </button>
          </div>
        ))}
      </div>
    </>
  );
}
