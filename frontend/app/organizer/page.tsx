"use client";
import Image from "next/image";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
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
  async function load() {
    try {
      setEvents(await api("/organizer/events"));
    } catch (e: any) {
      setError(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);
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
        throw new Error("A integração com o TMDb não está configurada.");
      }
      setCatalog(r.items);
      setCatalogStatus(r.items.length > 0 ? "success" : "empty");
    } catch (e: any) {
      setCatalog([]);
      setCatalogStatus("idle");
      setError(e.message);
    }
  }
  async function create(e: any) {
    e.preventDefault();
    try {
      await api("/organizer/events", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          starts_at: new Date(form.starts_at).toISOString(),
          capacity: Number(form.capacity),
          price_cents: Number(form.price_cents),
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
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
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
      {error && (
        <div className="status bad" style={{ marginBottom: 16 }}>
          {error}
        </div>
      )}
      <div className="grid">
        <div className="card">
          <h2>Encontre um filme do TMDb</h2>
          <div className="row">
            <input
              value={q}
              placeholder="Digite o nome do filme"
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
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
            {form.image_url && (
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
              />
            </label>
            <label>
              Descrição
              <textarea
                value={form.description}
                onChange={(e) =>
                  setForm({ ...form, description: e.target.value })
                }
              />
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
                required
              />
            </label>
            <label>
              Local
              <input
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
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
              />
            </label>
            <button className="btn accent">Publicar evento</button>
          </form>
        </div>
      </div>
      <div style={{ marginTop: 18 }} className="grid">
        {events.map((e) => (
          <div className="card" key={e.id}>
            {e.image_url && (
              <Image
                src={e.image_url}
                alt={`Pôster de ${e.title}`}
                width={500}
                height={750}
                className="event-card-image"
              />
            )}
            <span className="pill">
              {e.published ? "publicado" : "rascunho"}
            </span>
            <h3>{e.title}</h3>
            <p className="muted">
              {e.location} · R$ {(e.price_cents / 100).toFixed(2)}
            </p>
          </div>
        ))}
      </div>
    </>
  );
}
