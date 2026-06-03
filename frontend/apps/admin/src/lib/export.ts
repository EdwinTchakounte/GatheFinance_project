/**
 * Utilitaires d'export client-side :
 *   • CSV (RFC 4180, séparateur configurable, BOM UTF-8 pour Excel)
 *   • PDF via `window.print()` sur une fenêtre dédiée (le user choisit
 *     "Enregistrer au format PDF" dans le dialogue d'impression natif)
 *
 * Pas de dépendance externe — fonctionne hors-ligne, marche pour des
 * volumes raisonnables (< 50k lignes). Pour des exports massifs il faudrait
 * un endpoint backend qui streame.
 */

export type ExportColumn<T> = {
  /** Clé interne (utile pour debug) */
  key: string;
  /** Entête affichée */
  label: string;
  /** Sélecteur de valeur (raw → string). Reçoit la ligne entière. */
  value: (row: T) => string | number | null | undefined;
};


function _toCSVField(v: unknown, sep: string): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  // Échappement RFC 4180 : guillemets doubles + entoure si sep / \n / "
  if (s.includes(sep) || s.includes("\n") || s.includes('"')) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

/**
 * Exporte une liste vers un blob CSV et déclenche le téléchargement.
 * Excel-friendly : sep=";" + BOM UTF-8.
 */
export function exportCSV<T>({
  filename,
  columns,
  rows,
  separator = ";",
}: {
  filename: string;
  columns: ExportColumn<T>[];
  rows: T[];
  separator?: string;
}): void {
  const lines: string[] = [];
  // Header
  lines.push(columns.map((c) => _toCSVField(c.label, separator)).join(separator));
  // Body
  for (const r of rows) {
    lines.push(
      columns
        .map((c) => _toCSVField(c.value(r), separator))
        .join(separator),
    );
  }
  // BOM UTF-8 + CRLF pour Excel
  const csv = "﻿" + lines.join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}


/**
 * Ouvre une fenêtre d'impression avec un rendu HTML print-friendly de la
 * table. L'utilisateur peut choisir "Enregistrer au format PDF" dans le
 * dialogue natif du navigateur.
 *
 * Inclut un header (titre + sous-titre + date), une table classique, et
 * un footer paginé. Les styles `@page` impriment en A4 portrait.
 */
export function printPDF<T>({
  title,
  subtitle,
  columns,
  rows,
}: {
  title: string;
  subtitle?: string;
  columns: ExportColumn<T>[];
  rows: T[];
}): void {
  const escHtml = (s: string) =>
    s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  const head = columns
    .map((c) => `<th>${escHtml(c.label)}</th>`)
    .join("");
  const body = rows
    .map(
      (r) =>
        `<tr>${columns
          .map((c) => {
            const v = c.value(r);
            return `<td>${v === null || v === undefined ? "" : escHtml(String(v))}</td>`;
          })
          .join("")}</tr>`,
    )
    .join("");

  const today = new Date().toLocaleString("fr-FR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const html = `<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="utf-8" />
<title>${escHtml(title)}</title>
<style>
  @page { size: A4 portrait; margin: 1.5cm 1.2cm; }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1a1a1a;
    margin: 0;
    padding: 0;
  }
  header {
    border-bottom: 2px solid #1e407c;
    padding-bottom: 12px;
    margin-bottom: 20px;
  }
  header h1 {
    color: #1e407c;
    margin: 0 0 4px 0;
    font-size: 18pt;
  }
  header .meta {
    color: #666;
    font-size: 9pt;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 8.5pt;
  }
  th, td {
    border: 1px solid #ddd;
    padding: 6px 8px;
    text-align: left;
    vertical-align: top;
  }
  th {
    background: #f5f5ef;
    font-weight: 600;
    color: #1e407c;
  }
  tr:nth-child(even) td { background: #fafafa; }
  tfoot td {
    border: none;
    padding-top: 16px;
    color: #888;
    font-size: 8pt;
    text-align: right;
  }
  @media print {
    header { page-break-after: avoid; }
    thead { display: table-header-group; }
    tr { page-break-inside: avoid; }
  }
</style>
</head><body>
  <header>
    <h1>${escHtml(title)}</h1>
    ${subtitle ? `<p class="meta">${escHtml(subtitle)}</p>` : ""}
    <p class="meta">${rows.length} ligne(s) · Édité le ${escHtml(today)} · Gathé Finance</p>
  </header>
  <table>
    <thead><tr>${head}</tr></thead>
    <tbody>${body}</tbody>
    <tfoot><tr><td colspan="${columns.length}">Document généré par le dashboard admin Gathé Finance.</td></tr></tfoot>
  </table>
<script>
  window.addEventListener("load", function () {
    setTimeout(function () { window.print(); }, 200);
  });
</script>
</body></html>`;

  const w = window.open("", "_blank", "noopener");
  if (!w) {
    // bloqueur de popup — fallback : ouvrir un blob URL
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
    return;
  }
  w.document.open();
  w.document.write(html);
  w.document.close();
}
