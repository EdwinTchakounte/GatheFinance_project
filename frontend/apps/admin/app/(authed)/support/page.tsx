"use client";

import { useEffect, useRef, useState } from "react";
import { LifeBuoy } from "lucide-react";

import { buttonClasses } from "@/components/modal";
import {
  adminApi,
  type ApiError,
  type SupportThreadRow,
  type SupportThreadDetail,
} from "@/lib/api";


function fmt(iso: string | null): string {
  if (!iso) return "";
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


export default function SupportPage() {
  const [threads, setThreads] = useState<SupportThreadRow[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<SupportThreadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  async function loadThreads() {
    setError(null);
    try {
      const rows = await adminApi.support.threads();
      setThreads(rows);
      if (selected === null && rows.length > 0) {
        void openThread(rows[0]!.id);
      }
    } catch (err) {
      setError((err as ApiError).detail ?? "Chargement impossible.");
    } finally {
      setLoading(false);
    }
  }

  async function openThread(id: number) {
    setSelected(id);
    try {
      const d = await adminApi.support.thread(id);
      setDetail(d);
      requestAnimationFrame(() =>
        bottomRef.current?.scrollIntoView({ behavior: "smooth" }),
      );
      // La lecture côté staff a remis les non-lus à 0 : rafraîchir la liste.
      setThreads((prev) =>
        prev.map((t) => (t.id === id ? { ...t, staff_unread: 0 } : t)),
      );
    } catch (err) {
      setError((err as ApiError).detail ?? "Fil introuvable.");
    }
  }

  useEffect(() => {
    loadThreads();
    const t = setInterval(loadThreads, 30_000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onReply() {
    const body = draft.trim();
    if (!body || sending || selected === null) return;
    setSending(true);
    try {
      await adminApi.support.reply(selected, body);
      setDraft("");
      await openThread(selected);
      await loadThreads();
    } catch (err) {
      setError((err as ApiError).detail ?? "Envoi impossible.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div>
      <header className="mb-6">
        <span className="mb-1 inline-flex items-center gap-1.5 rounded bg-teal-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-teal-700">
          <LifeBuoy className="size-3" /> Support
        </span>
        <h1 className="mt-2 font-editorial text-3xl font-medium text-ink-900">
          Support membres
        </h1>
        <p className="mt-1 text-sm text-ink-500">
          Réponds aux messages des membres. Chaque réponse notifie le membre
          (in-app + push).
        </p>
      </header>

      {error ? (
        <div className="mb-5 rounded-md border border-terra-400/40 bg-terra-50/60 px-4 py-2.5 text-sm text-terra-700">
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-5 md:grid-cols-[320px_1fr]">
        {/* ── Liste des fils ── */}
        <aside className="rounded-xl border border-ink-100 bg-paper">
          {loading ? (
            <ul className="space-y-2 p-3">
              {[0, 1, 2].map((i) => (
                <li key={i} className="h-16 animate-pulse rounded-lg bg-cream" />
              ))}
            </ul>
          ) : threads.length === 0 ? (
            <p className="p-6 text-center text-sm text-ink-500">
              Aucun message pour le moment.
            </p>
          ) : (
            <ul className="max-h-[64vh] divide-y divide-ink-100 overflow-y-auto">
              {threads.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    onClick={() => openThread(t.id)}
                    className={[
                      "block w-full px-4 py-3 text-left transition",
                      selected === t.id ? "bg-teal-50" : "hover:bg-cream",
                    ].join(" ")}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-ink-900">
                        {t.member_nom || t.member_numero}
                      </span>
                      {t.staff_unread > 0 ? (
                        <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-teal-600 px-1.5 text-[11px] font-bold text-white">
                          {t.staff_unread}
                        </span>
                      ) : null}
                    </div>
                    <p className="truncate text-xs text-ink-500">
                      {t.member_numero} · {fmt(t.last_message_at)}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-ink-600">
                      {t.last_body}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* ── Conversation ── */}
        <section className="flex min-h-[64vh] flex-col rounded-xl border border-ink-100 bg-paper">
          {detail === null ? (
            <div className="flex flex-1 items-center justify-center text-sm text-ink-400">
              Sélectionne un fil à gauche.
            </div>
          ) : (
            <>
              <div className="border-b border-ink-100 px-5 py-3">
                <p className="text-sm font-semibold text-ink-900">
                  {detail.member_nom}
                </p>
                <p className="text-xs text-ink-500">{detail.member_numero}</p>
              </div>
              <div className="flex-1 space-y-3 overflow-y-auto p-5">
                {detail.messages.map((m) => {
                  const staff = m.sender === "staff";
                  return (
                    <div
                      key={m.id}
                      className={`flex ${staff ? "justify-end" : "justify-start"}`}
                    >
                      <div className="max-w-[78%] space-y-1">
                        <div
                          className={[
                            "whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm",
                            staff
                              ? "rounded-br-sm bg-teal-600 text-white"
                              : "rounded-bl-sm border border-ink-100 bg-cream text-ink-900",
                          ].join(" ")}
                        >
                          {m.body}
                        </div>
                        <p
                          className={`text-[11px] text-ink-400 ${staff ? "text-right" : "text-left"}`}
                        >
                          {staff ? "Support" : detail.member_nom} ·{" "}
                          {fmt(m.created_at)}
                        </p>
                      </div>
                    </div>
                  );
                })}
                <div ref={bottomRef} />
              </div>
              <div className="flex items-end gap-3 border-t border-ink-100 p-4">
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      onReply();
                    }
                  }}
                  rows={1}
                  placeholder="Répondre au membre…"
                  className="max-h-32 min-h-[44px] flex-1 resize-none rounded-lg border border-ink-200 bg-cream px-4 py-3 text-sm text-ink-900 outline-none focus:border-teal-500"
                />
                <button
                  type="button"
                  onClick={onReply}
                  disabled={sending || !draft.trim()}
                  className={buttonClasses({ variant: "primary", size: "md" }) + " disabled:opacity-50"}
                >
                  {sending ? "…" : "Répondre"}
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
