"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../../../lib/api";

type Checkout = {
  id: string;
  status: string;
  checkout_url: string | null;
  event_id: number;
  event_title: string;
  event_type: string;
  quantity: number;
  seat_labels: string[];
  amount_cents: number;
  currency: string;
  expires_at: string;
  ticket_ids: number[];
};

const statusLabels: Record<string, string> = {
  pending: "Aguardando pagamento",
  processing: "Pagamento em processamento",
  paid: "Pagamento aprovado",
  failed: "Pagamento não aprovado",
  cancelled: "Compra cancelada",
  expired: "Checkout expirado",
  refunded: "Pagamento reembolsado",
  partially_refunded: "Pagamento parcialmente reembolsado",
};

export default function CheckoutPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [checkout, setCheckout] = useState<Checkout | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const returnHandled = useRef(false);

  const loadCheckout = useCallback(async () => {
    const data = await api(`/checkout/sessions/${id}`);
    setCheckout(data);
    return data as Checkout;
  }, [id]);

  useEffect(() => {
    if (returnHandled.current) return;
    returnHandled.current = true;

    async function initialize() {
      setError("");
      try {
        const sessionId = searchParams.get("session_id");
        if (searchParams.get("success") === "1" && sessionId) {
          setCheckout(
            await api(`/checkout/sessions/${id}/sync`, {
              method: "POST",
              body: JSON.stringify({ session_id: sessionId }),
            }),
          );
        } else if (searchParams.get("cancelled") === "1") {
          setCheckout(
            await api(`/checkout/sessions/${id}/cancel`, { method: "POST" }),
          );
        } else {
          await loadCheckout();
        }
      } catch (caughtError) {
        setError(getErrorMessage(caughtError));
      } finally {
        setLoading(false);
        if (searchParams.toString()) router.replace(`/checkout/${id}`);
      }
    }

    initialize();
  }, [id, loadCheckout, router, searchParams]);

  useEffect(() => {
    if (!checkout || !["pending", "processing"].includes(checkout.status)) {
      return;
    }
    const interval = window.setInterval(() => {
      loadCheckout().catch((caughtError) => {
        setError(getErrorMessage(caughtError));
      });
    }, 3000);
    return () => window.clearInterval(interval);
  }, [checkout, loadCheckout]);

  async function cancelCheckout() {
    if (!window.confirm("Deseja cancelar esta compra e liberar os ingressos?")) {
      return;
    }
    setCancelling(true);
    setError("");
    try {
      setCheckout(
        await api(`/checkout/sessions/${id}/cancel`, { method: "POST" }),
      );
    } catch (caughtError) {
      setError(getErrorMessage(caughtError));
    } finally {
      setCancelling(false);
    }
  }

  if (loading) return <div className="card">Preparando checkout…</div>;

  if (!checkout) {
    return (
      <div className="card checkout-state-card">
        <h1>Não foi possível abrir a compra</h1>
        <div className="status bad">{error || "Checkout não encontrado."}</div>
        <Link className="btn ghost" href="/events">
          Voltar aos eventos
        </Link>
      </div>
    );
  }

  const total = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: checkout.currency.toUpperCase(),
  }).format(checkout.amount_cents / 100);
  const isPending = checkout.status === "pending";
  const isPaid = checkout.status === "paid";
  const showTestPanel = isPending && checkout.amount_cents > 0;
  const statusTone = isPaid
    ? "ok"
    : ["failed", "cancelled", "expired"].includes(checkout.status)
      ? "bad"
      : "checkout-status-neutral";

  return (
    <div className="checkout-page">
      <div className="hero checkout-hero">
        <div>
          <div className="eyebrow">Checkout seguro</div>
          <h1>{checkout.event_title}</h1>
          <p className="muted">
            Revise a compra antes de ir para o pagamento.
          </p>
        </div>
        <span className={`status ${statusTone}`}>
          {statusLabels[checkout.status] || checkout.status}
        </span>
      </div>

      {error && <div className="status bad checkout-feedback">{error}</div>}

      <div className={`checkout-grid ${showTestPanel ? "" : "single"}`}>
        <section className="card checkout-summary">
          <div>
            <span className="muted">Evento</span>
            <b>{checkout.event_title}</b>
          </div>
          <div>
            <span className="muted">Ingressos</span>
            <b>{checkout.quantity}</b>
          </div>
          {checkout.seat_labels.length > 0 && (
            <div>
              <span className="muted">Assentos</span>
              <b>{checkout.seat_labels.join(", ")}</b>
            </div>
          )}
          <div className="checkout-total">
            <span>Total</span>
            <strong>{total}</strong>
          </div>
          {isPending && (
            <p className="muted checkout-expiration">
              Os ingressos ficam reservados até{" "}
              {new Date(checkout.expires_at).toLocaleString("pt-BR")}.
            </p>
          )}

          {isPending && checkout.checkout_url && (
            <div className="checkout-actions">
              <button
                type="button"
                className="btn primary"
                onClick={() => window.location.assign(checkout.checkout_url!)}
              >
                Pagar no ambiente da Stripe
              </button>
              <button
                type="button"
                className="btn ghost"
                disabled={cancelling}
                onClick={cancelCheckout}
              >
                {cancelling ? "Cancelando…" : "Cancelar compra"}
              </button>
            </div>
          )}

          {isPaid && (
            <div className="checkout-actions">
              <Link className="btn primary" href="/tickets">
                Ver meus ingressos
              </Link>
              <Link className="btn ghost" href="/events">
                Ver outros eventos
              </Link>
            </div>
          )}

          {["failed", "cancelled", "expired"].includes(checkout.status) && (
            <div className="checkout-actions">
              <Link className="btn primary" href={`/events/${checkout.event_id}`}>
                Tentar novamente
              </Link>
              <Link className="btn ghost" href="/events">
                Voltar aos eventos
              </Link>
            </div>
          )}
        </section>

        {showTestPanel && (
          <aside className="card stripe-test-card">
            <div className="pill">AMBIENTE DE TESTE</div>
            <h2>Simule o resultado</h2>
            <p className="muted">
              Nenhuma cobrança real será realizada. Na Stripe, use qualquer
              data futura e qualquer CVC de três dígitos.
            </p>
            <div className="test-payment-option">
              <span>Compra aprovada</span>
              <code>4242 4242 4242 4242</code>
            </div>
            <div className="test-payment-option">
              <span>Recusa genérica</span>
              <code>4000 0000 0000 0002</code>
            </div>
            <div className="test-payment-option">
              <span>Saldo insuficiente</span>
              <code>4000 0000 0000 9995</code>
            </div>
            <p className="muted stripe-test-note">
              Use somente os cartões de teste.
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}
