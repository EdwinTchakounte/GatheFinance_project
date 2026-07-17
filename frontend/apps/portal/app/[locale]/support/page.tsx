"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { Container } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type PortalSupportMessage,
} from "@/lib/api";


function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}


export default function PortalSupportPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<PortalSupportMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  async function load(scroll = false) {
    try {
      portalApi.primeCsrf().catch(() => undefined);
      const res = await portalApi.support.thread();
      setMessages(res.messages);
      if (scroll) {
        requestAnimationFrame(() =>
          bottomRef.current?.scrollIntoView({ behavior: "smooth" }),
        );
      }
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.status === 401 || apiErr.status === 403) {
        router.replace("/connexion");
        return;
      }
      setError(apiErr.detail ?? "Impossible de charger la conversation.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(true);
    // Polling léger : voit les réponses du support sans rafraîchir la page.
    const t = setInterval(() => load(false), 30_000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSend() {
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    try {
      await portalApi.support.send(body);
      setDraft("");
      await load(true);
    } catch (err) {
      setError((err as ApiError).detail ?? "Envoi impossible. Réessaie.");
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="min-h-[60vh] py-10">
      <Container width="content">
        <header className="mb-6 space-y-1">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-terra-600">
            Espace membre
          </p>
          <h1 className="font-display text-3xl text-ink-900">Support</h1>
          <p className="text-sm text-ink-500">
            Laisse ton message ici, le support te répond directement dans ce
            fil (tu seras aussi notifié·e).
          </p>
        </header>

        {error ? (
          <div className="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            {error}
          </div>
        ) : null}

        <div className="rounded-2xl border border-ink-100 bg-paper">
          {/* Fil de messages */}
          <div className="max-h-[52vh] space-y-3 overflow-y-auto p-5">
            {loading ? (
              <ul className="space-y-3">
                {[0, 1, 2].map((i) => (
                  <li
                    key={i}
                    className="h-14 animate-pulse rounded-2xl bg-cream"
                  />
                ))}
              </ul>
            ) : messages.length === 0 ? (
              <div className="py-12 text-center">
                <p className="font-display text-lg text-ink-900">
                  Besoin d&apos;aide ?
                </p>
                <p className="mt-1 text-sm text-ink-500">
                  Écris ton premier message ci-dessous.
                </p>
              </div>
            ) : (
              messages.map((m) => <Bubble key={m.id} msg={m} />)
            )}
            <div ref={bottomRef} />
          </div>

          {/* Barre de saisie */}
          <div className="flex items-end gap-3 border-t border-ink-100 p-4">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSend();
                }
              }}
              rows={1}
              placeholder="Écris un message…"
              className="max-h-32 min-h-[44px] flex-1 resize-none rounded-2xl border border-ink-200 bg-cream px-4 py-3 text-sm text-ink-900 outline-none focus:border-teal-500"
            />
            <button
              type="button"
              onClick={onSend}
              disabled={sending || !draft.trim()}
              className="inline-flex h-11 items-center rounded-full bg-teal-600 px-5 text-sm font-semibold text-white transition disabled:opacity-50"
            >
              {sending ? "…" : "Envoyer"}
            </button>
          </div>
        </div>
      </Container>
    </main>
  );
}


function Bubble({ msg }: { msg: PortalSupportMessage }) {
  const mine = msg.sender === "member";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[78%] space-y-1">
        <div
          className={[
            "whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm",
            mine
              ? "rounded-br-sm bg-teal-600 text-white"
              : "rounded-bl-sm border border-ink-100 bg-cream text-ink-900",
          ].join(" ")}
        >
          {msg.body}
        </div>
        <p
          className={`text-[11px] text-ink-400 ${mine ? "text-right" : "text-left"}`}
        >
          {mine ? "Vous" : "Support"} · {fmtTime(msg.created_at)}
        </p>
      </div>
    </div>
  );
}
