"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, MessageSquare, Send } from "lucide-react";

import { portalApi, type PortalComment, type SocialKind } from "@/lib/api";

function fmt(d: string): string {
  return new Date(d).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "2-digit",
  });
}

export function CommentsSection({ kind, id }: { kind: SocialKind; id: number }) {
  const [rows, setRows] = useState<PortalComment[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replyTo, setReplyTo] = useState<PortalComment | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    portalApi.social
      .comments(kind, id, { limit: 50 })
      .then((data) => {
        setRows(data.results);
        setCount(data.count);
      })
      .catch(() => setError("Impossible de charger les commentaires."))
      .finally(() => setLoading(false));
  }, [kind, id]);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <section className="rounded-md border border-line-200 bg-paper p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-ink-900">
        <MessageSquare className="size-4 text-blue-700" aria-hidden="true" />
        Commentaires
        <span className="text-ink-500">· {count}</span>
      </h2>

      <div className="mt-4">
        <Composer
          kind={kind}
          id={id}
          replyTo={replyTo}
          onCancelReply={() => setReplyTo(null)}
          onPosted={() => {
            setReplyTo(null);
            reload();
          }}
        />
      </div>

      <div className="mt-5 space-y-4">
        {loading ? (
          <p className="text-sm text-ink-500">Chargement…</p>
        ) : error ? (
          <p className="text-sm text-terra-700">{error}</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-ink-500">
            Aucun commentaire pour l&apos;instant. Soyez le premier à réagir.
          </p>
        ) : (
          rows.map((c) => (
            <CommentThread key={c.id} c={c} onReply={() => setReplyTo(c)} />
          ))
        )}
      </div>
    </section>
  );
}

function CommentThread({ c, onReply }: { c: PortalComment; onReply: () => void }) {
  return (
    <div>
      <CommentBubble c={c} onReply={onReply} />
      {c.replies?.length ? (
        <div className="mt-2 space-y-2 border-l border-line-200 pl-4">
          {c.replies.map((r) => (
            <CommentBubble key={r.id} c={r} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function CommentBubble({ c, onReply }: { c: PortalComment; onReply?: () => void }) {
  return (
    <div className="rounded-md border border-line-200 bg-cream/40 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold text-ink-900">
          {c.author_name || "Membre"}
        </p>
        <span className="text-[0.65rem] text-ink-500">{fmt(c.created_at)}</span>
      </div>
      <p className="mt-1 whitespace-pre-wrap text-sm text-ink-700">{c.body}</p>
      {onReply ? (
        <button
          type="button"
          onClick={onReply}
          className="mt-1 text-xs font-medium text-blue-700 hover:underline"
        >
          Répondre
        </button>
      ) : null}
    </div>
  );
}

function Composer({
  kind,
  id,
  replyTo,
  onCancelReply,
  onPosted,
}: {
  kind: SocialKind;
  id: number;
  replyTo: PortalComment | null;
  onCancelReply: () => void;
  onPosted: () => void;
}) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    const text = body.trim();
    if (!text || busy) return;
    setBusy(true);
    setErr(null);
    try {
      await portalApi.social.postComment(kind, id, text, replyTo?.id);
      setBody("");
      onPosted();
    } catch (e) {
      setErr((e as { detail?: string }).detail ?? "Envoi impossible.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border border-line-200 bg-paper p-3">
      {replyTo ? (
        <div className="mb-2 flex items-center justify-between rounded bg-blue-50/60 px-2 py-1 text-xs text-blue-800">
          <span>En réponse à {replyTo.author_name || "un membre"}</span>
          <button
            type="button"
            onClick={onCancelReply}
            className="font-semibold hover:underline"
          >
            Annuler
          </button>
        </div>
      ) : null}
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={2}
        placeholder={replyTo ? "Votre réponse…" : "Ajouter un commentaire…"}
        className="block w-full resize-y rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-900 outline-none focus:border-blue-700 focus:ring-1 focus:ring-blue-700"
      />
      {err ? <p className="mt-1 text-xs text-terra-700">{err}</p> : null}
      <div className="mt-2 flex justify-end">
        <button
          type="button"
          onClick={submit}
          disabled={busy || !body.trim()}
          className="inline-flex items-center gap-1.5 rounded-md bg-blue-700 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-50"
        >
          {busy ? (
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <Send className="size-4" aria-hidden="true" />
          )}
          Publier
        </button>
      </div>
    </div>
  );
}
