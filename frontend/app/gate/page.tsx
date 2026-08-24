"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import { Html5Qrcode } from "html5-qrcode";

const resultLabels: Record<string, string> = {
  valid: "Válido",
  invalid: "Inválido",
  already_used: "Já utilizado",
  event_wrong: "Evento incorreto",
};

export default function Gate() {
  const [code, setCode] = useState("");
  const [eventId, setEventId] = useState("1");
  const [result, setResult] = useState<any>();
  const [events, setEvents] = useState<any[]>([]);
  const scanner = useRef<Html5Qrcode | null>(null);
  useEffect(() => {
    api("/events")
      .then((loadedEvents: any[]) => {
        const sortedEvents = [...loadedEvents].sort((first, second) =>
          first.title.localeCompare(second.title, "pt-BR", {
            sensitivity: "base",
          }),
        );
        setEvents(sortedEvents);
        setEventId((current) =>
          sortedEvents.some((event) => String(event.id) === current)
            ? current
            : String(sortedEvents[0]?.id ?? ""),
        );
      })
      .catch(() => {});
    return () => {
      scanner.current?.stop().catch(() => {});
    };
  }, []);
  async function validate(c = code) {
    try {
      setResult(
        await api("/gate/validate", {
          method: "POST",
          body: JSON.stringify({ code: c, event_id: Number(eventId) }),
        }),
      );
    } catch (e: any) {
      setResult({ result: "invalid", message: e.message });
    }
  }
  async function start() {
    if (scanner.current) return;
    const s = new Html5Qrcode("reader");
    scanner.current = s;
    await s.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: 220 },
      (decoded) => {
        setCode(decoded);
        validate(decoded);
        s.stop().catch(() => {});
        scanner.current = null;
      },
      () => {},
    );
  }
  return (
    <>
      <div className="hero">
        <div>
          <div className="eyebrow">Controle de acesso</div>
          <h1>Portaria.</h1>
          <p className="muted">
            Leitura pela câmera e fallback por digitação manual.
          </p>
        </div>
      </div>
      <div className="grid">
        <div className="card">
          <label>
            Evento
            <select
              value={eventId}
              onChange={(e) => setEventId(e.target.value)}
            >
              {events.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.title}
                </option>
              ))}
            </select>
          </label>
          <label style={{ marginTop: 14 }}>
            Código manual
            <input value={code} onChange={(e) => setCode(e.target.value)} />
          </label>
          <div
            className="row"
            style={{ justifyContent: "flex-start", marginTop: 14 }}
          >
            <button className="btn primary" onClick={() => validate()}>
              Validar
            </button>
            <button className="btn ghost" onClick={start}>
              Abrir câmera
            </button>
          </div>
          <div id="reader" style={{ marginTop: 16 }} />
        </div>
        <div className="card">
          {result ? (
            <div
              className={`status ${result.result === "valid" ? "ok" : "bad"}`}
            >
              <div style={{ fontSize: 28, textTransform: "uppercase" }}>
                {resultLabels[result.result] ?? "Resultado desconhecido"}
              </div>
              <div>{result.message}</div>
            </div>
          ) : (
            <p className="muted">A resposta aparecerá aqui.</p>
          )}
        </div>
      </div>
    </>
  );
}
