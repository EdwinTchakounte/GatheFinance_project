"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
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
      /* z-[60] : la preview doit passer AU-DESSUS d'une `Modal` (z-50) quand
         elle est ouverte depuis une modale de détail (adhésion, crédit…). */
      className="fixed inset-0 z-[60] flex flex-col bg-ink-900/85 backdrop-blur-sm"
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

// ---------------------------------------------------------------------------
// Provider global — ouvrir un aperçu depuis n'importe quelle profondeur
// ---------------------------------------------------------------------------

/**
 * Beaucoup de pièces jointes sont rendues par des sous-composants imbriqués
 * (badges de profil, sections garantie, lignes de tableau…). Faire remonter un
 * état de preview jusqu'à la page à chaque fois est bruyant et pousse à
 * retomber sur `target="_blank"`. Ce provider expose un `openDocument()`
 * utilisable partout ; la modale est montée une seule fois dans le layout.
 */

export type OpenDocumentArgs = {
  url: string;
  name: string;
  subtitle?: string;
};

const DocumentPreviewContext = createContext<
  ((doc: OpenDocumentArgs) => void) | null
>(null);

export function DocumentPreviewProvider({ children }: { children: ReactNode }) {
  const [doc, setDoc] = useState<OpenDocumentArgs | null>(null);
  const open = useCallback((next: OpenDocumentArgs) => setDoc(next), []);
  const value = useMemo(() => open, [open]);

  return (
    <DocumentPreviewContext.Provider value={value}>
      {children}
      {doc && (
        <DocumentPreview
          url={doc.url}
          name={doc.name}
          subtitle={doc.subtitle}
          onClose={() => setDoc(null)}
        />
      )}
    </DocumentPreviewContext.Provider>
  );
}

/**
 * Retourne `openDocument(doc)`. Hors provider, on retombe sur l'ouverture
 * navigateur plutôt que de planter — mais toutes les pages admin sont sous le
 * layout `(authed)` qui monte le provider.
 */
export function useDocumentPreview(): (doc: OpenDocumentArgs) => void {
  const ctx = useContext(DocumentPreviewContext);
  return (
    ctx ??
    ((doc: OpenDocumentArgs) => {
      window.open(doc.url, "_blank", "noopener,noreferrer");
    })
  );
}

/**
 * Bouton compact « voir la pièce » — remplace les anciens liens
 * `target="_blank"` disséminés dans les pages.
 */
export function DocumentLink({
  url,
  name,
  subtitle,
  label = "Voir",
  className,
}: {
  url: string;
  name: string;
  subtitle?: string;
  label?: string;
  className?: string;
}) {
  const openDocument = useDocumentPreview();
  return (
    <button
      type="button"
      onClick={() => openDocument({ url, name, subtitle })}
      title={name}
      className={
        className ??
        "inline-flex items-center gap-1 font-medium text-blue-700 hover:underline"
      }
    >
      <FileText className="size-3" aria-hidden="true" />
      {label}
    </button>
  );
}
