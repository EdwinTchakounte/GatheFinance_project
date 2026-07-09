"use client";

import { useEffect, useState } from "react";
import { Heart } from "lucide-react";

import { portalApi, type SocialKind } from "@/lib/api";

export function LikeButton({ kind, id }: { kind: SocialKind; id: number }) {
  const [liked, setLiked] = useState(false);
  const [count, setCount] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    portalApi.social
      .reaction(kind, id)
      .then((r) => {
        if (!alive) return;
        setLiked(r.liked);
        setCount(r.count);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [kind, id]);

  async function toggle() {
    if (busy) return;
    setBusy(true);
    try {
      const r = await portalApi.social.toggleLike(kind, id);
      setLiked(r.liked);
      setCount(r.count);
    } catch {
      // silencieux — l'état reste inchangé.
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy}
      aria-pressed={liked}
      className={
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-60 " +
        (liked
          ? "border-terra-400/40 bg-terra-50/60 text-terra-700"
          : "border-line-200 bg-paper text-ink-700 hover:border-terra-400/40")
      }
    >
      <Heart
        className={"size-4 " + (liked ? "fill-terra-500 text-terra-500" : "")}
        aria-hidden="true"
      />
      {count}
    </button>
  );
}
