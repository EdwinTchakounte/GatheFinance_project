"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Container } from "@gathe/ui";

import {
  portalApi,
  type ApiError,
  type PortalAnnouncement,
} from "@/lib/api";


export default function PortalAnnouncementsPage() {
  const router = useRouter();
  const [items, setItems] = useState<PortalAnnouncement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        portalApi.primeCsrf().catch(() => undefined);
        const res = await portalApi.notifications.announcements();
        if (alive) setItems(res.results);
      } catch (err) {
        const apiErr = err as ApiError;
        if (apiErr.status === 401 || apiErr.status === 403) {
          router.replace("/connexion");
          return;
        }
        if (alive) setError(apiErr.detail ?? "Impossible de charger les annonces.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [router]);

  return (
    <main className="min-h-[60vh] py-10">
      <Container width="content">
        <header className="mb-6 space-y-1">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-terra-600">
            Espace membre
          </p>
          <h1 className="font-display text-3xl text-ink-900">Annonces</h1>
          <p className="text-sm text-ink-500">
            Les communications de la coopérative, avec leurs pièces jointes.
          </p>
        </header>

        {error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            {error}
          </div>
        ) : loading ? (
          <ul className="space-y-4">
            {[0, 1, 2].map((i) => (
              <li
                key={i}
                className="h-40 animate-pulse rounded-2xl border border-ink-100 bg-paper"
              />
            ))}
          </ul>
        ) : items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-ink-200 bg-cream p-10 text-center text-sm text-ink-500">
            Aucune annonce pour le moment.
          </div>
        ) : (
          <ul className="space-y-5">
            {items.map((a) => (
              <li
                key={a.id}
                className="overflow-hidden rounded-2xl border border-ink-100 bg-paper shadow-sm"
              >
                {a.image_url ? (
                  <a href={a.image_url} target="_blank" rel="noopener noreferrer">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={a.image_url}
                      alt=""
                      className="max-h-80 w-full object-cover"
                    />
                  </a>
                ) : null}
                <div className="space-y-2 p-5">
                  <div className="flex items-baseline justify-between gap-3">
                    <h2 className="font-display text-lg text-ink-900">{a.titre}</h2>
                    {a.published_at ? (
                      <span className="shrink-0 text-xs text-ink-400">
                        {new Date(a.published_at).toLocaleDateString("fr-FR", {
                          day: "2-digit",
                          month: "short",
                          year: "numeric",
                        })}
                      </span>
                    ) : null}
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
                    {a.corps}
                  </p>
                  {a.image_url ? (
                    <a
                      href={a.image_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-terra-700 hover:underline"
                    >
                      Voir la pièce jointe →
                    </a>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Container>
    </main>
  );
}
