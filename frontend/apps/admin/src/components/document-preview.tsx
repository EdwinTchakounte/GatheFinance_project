"use client";

import { useEffect, type ReactNode } from "react";
import { Download, FileText, X, ZoomIn } from "lucide-react";

/**
 * Composants génériques de preview de documents pour le dashboard admin.
 *
 * - `DocumentThumbnail` : miniature cliquable, affiche l'image inline ou
 *   l'icône fichier selon l'extension.
 * - `DocumentPreview` : modale plein écran, image inline pour les formats
 *   image, `<iframe>` natif pour les PDF, message + lien téléchargement
 *   sinon. Esc / clic backdrop / bouton Fermer pour quitter.
 *
 * Le but est de couvrir TOUTES les pièces uploadées (CNI, plan de loc,
 * contrat CGA, certificat CFP, BRC, paiements, etc.) sans qu'aucune page
 * admin ne ré-implémente sa propre modale.
 */

const IMAGE_EXT = /\.(png|jpe?g|gif|webp|bmp|svg)(\?|$)/i;
const PDF_EXT = /\.pdf(\?|$)/i;

function isImageUrl(url: string): boolean {
  return IMAGE_EXT.test(url);
}

function isPdfUrl(url: string): boolean {
  return PDF_EXT.test(url);
}

// ---------------------------------------------------------------------------
// Thumbnail
// ---------------------------------------------------------------------------

export type DocumentThumbnailSize = "sm" | "md";

const THUMB_SIZES: Record<DocumentThumbnailSize, string> = {
  sm: "h-16 w-14",
  md: "h-24 w-20",
};

export function DocumentThumbnail({
  url,
  label,
  onOpen,
  size = "md",
}: {
  url: string | null | undefined;
  label: string;
  onOpen: () => void;
  size?: DocumentThumbnailSize;
}) {
  const dims = THUMB_SIZES[size];
  if (!url) {
    return (
      <div
        className={`flex ${dims} shrink-0 items-center justify-center rounded-md border border-dashed border-line-200 bg-paper-soft text-xs text-ink-400`}
      >
        Aucun
      </div>
    );
  }
  const asImage = isImageUrl(url);
  return (
    <button
      type="button"
      onClick={onOpen}
      className={`group relative ${dims} shrink-0 overflow-hidden rounded-md border border-line-200 bg-paper-soft transition-shadow hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-700`}
      title="Cliquer pour ouvrir le document en plein écran"
    >
      {asImage ? (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img src={url} alt={label} className="h-full w-full object-cover" />
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-ink-500">
          <FileText className="h-7 w-7" />
          <span className="text-[10px] uppercase tracking-wide">
            {(url.split(".").pop() || "?").toUpperCase().slice(0, 4)}
          </span>
        </div>
      )}
      <span className="absolute inset-0 flex items-center justify-center bg-ink-900/0 opacity-0 transition-all group-hover:bg-ink-900/30 group-hover:opacity-100">
        <ZoomIn className="h-5 w-5 text-white" />
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Preview modale plein écran
// ---------------------------------------------------------------------------

export function DocumentPreview({
  url,
  name,
  subtitle,
  onClose,
  extraActions,
}: {
  url: string;
  name: string;
  subtitle?: string;
  onClose: () => void;
  extraActions?: ReactNode;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const asImage = isImageUrl(url);
  const asPdf = isPdfUrl(url);

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      className="fixed inset-0 z-50 flex flex-col bg-ink-900/85 backdrop-blur-sm"
    >
      <header className="flex items-center justify-between border-b border-white/10 px-6 py-3 text-paper">
        <div className="min-w-0">
          {subtitle && (
            <p className="truncate text-sm font-semibold">{subtitle}</p>
          )}
          <p
            className={`truncate text-xs ${
              subtitle ? "text-paper/60" : "text-paper font-semibold"
            }`}
          >
            {name}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {extraActions}
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1.5 rounded-md bg-white/10 px-3 py-1.5 text-xs font-medium text-paper hover:bg-white/20"
          >
            <Download className="h-3.5 w-3.5" />
            Télécharger
          </a>
          <button
            onClick={onClose}
            className="inline-flex items-center gap-1.5 rounded-md bg-white/10 px-3 py-1.5 text-xs font-medium text-paper hover:bg-white/20"
          >
            <X className="h-3.5 w-3.5" />
            Fermer (Esc)
          </button>
        </div>
      </header>
      <div
        onClick={(e) => e.stopPropagation()}
        className="flex flex-1 items-center justify-center overflow-auto p-6"
      >
        {asImage ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={url}
            alt={name}
            className="max-h-full max-w-full rounded-md bg-paper shadow-2xl"
          />
        ) : asPdf ? (
          <iframe
            src={url}
            title={name}
            className="h-full w-full max-w-4xl rounded-md bg-paper"
          />
        ) : (
          <div className="rounded-md bg-paper p-8 text-center">
            <FileText className="mx-auto h-12 w-12 text-ink-400" />
            <p className="mt-3 text-sm text-ink-700">
              Aperçu non supporté pour ce type de fichier.
            </p>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:underline"
            >
              <Download className="h-4 w-4" />
              Télécharger le fichier
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
