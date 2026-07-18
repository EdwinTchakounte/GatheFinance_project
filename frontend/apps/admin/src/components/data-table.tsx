"use client";

import { EmptyState } from "@gathe/ui";
import { Inbox } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { ColumnsMenu } from "@/components/columns-menu";
import { ExportMenu } from "@/components/export-menu";
import type { ExportColumn } from "@/lib/export";

/**
 * Tableau admin réutilisable — reprend le pattern éprouvé sur `/members` :
 *   • sélecteur de colonnes visibles (ColumnsMenu)
 *   • ligne de filtres PAR COLONNE (texte = « contient » ; numérique = seuil ≥)
 *   • pied de total pour les colonnes numériques
 *   • export CSV/PDF des colonnes visibles + lignes filtrées
 *   • rendu « soft » unifié via la classe globale `table-admin` + pills
 *
 * On le pose sur tous les tableaux de listing pour un rendu cohérent et des
 * filtres homogènes (retraits, paiements, reconductions, carnets, BRC…).
 */
export type DataColumn<T> = {
  key: string;
  label: string;
  /** Toujours visible (non désactivable dans le menu colonnes). */
  locked?: boolean;
  /** Visible par défaut (sinon masquée jusqu'à activation). Défaut : true. */
  defaultVisible?: boolean;
  /** Colonne numérique : filtre = seuil minimum ≥, total en pied. */
  numeric?: boolean;
  align?: "right";
  /** Désactive le champ de filtre pour cette colonne. Défaut : filtrable. */
  filterable?: boolean;
  /** Valeur brute (filtre + export + total). */
  text: (row: T) => string;
  /** Rendu riche ; par défaut affiche `text(row)`. */
  render?: (row: T) => ReactNode;
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  actions,
  actionsLabel = "Actions",
  showTotals = true,
  emptyLabel = "Aucune ligne.",
  filteredEmptyLabel = "Aucune ligne ne correspond aux filtres de colonne.",
  leftMeta,
  onRowClick,
  exportFilename,
  exportTitle,
  exportSubtitle,
}: {
  columns: DataColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  /** Rendu des actions par ligne (colonne finale non filtrable). */
  actions?: (row: T) => ReactNode;
  actionsLabel?: string;
  showTotals?: boolean;
  emptyLabel?: string;
  filteredEmptyLabel?: string;
  /** Contenu libre à gauche de la barre d'outils (ex. compteur). */
  leftMeta?: ReactNode;
  /** Rend la ligne cliquable (ex. ouvrir un drawer/détail). */
  onRowClick?: (row: T) => void;
  exportFilename?: string;
  exportTitle?: string;
  exportSubtitle?: string;
}) {
  const [visible, setVisible] = useState<Set<string>>(
    () =>
      new Set(
        columns.filter((c) => c.defaultVisible !== false).map((c) => c.key),
      ),
  );
  const [colFilters, setColFilters] = useState<Record<string, string>>({});

  const shownCols = columns.filter((c) => visible.has(c.key));

  const filtered = useMemo(() => {
    const active = Object.entries(colFilters).filter(([, v]) => v.trim() !== "");
    if (active.length === 0) return rows;
    return rows.filter((row) =>
      active.every(([key, raw]) => {
        const col = columns.find((c) => c.key === key);
        if (!col) return true;
        if (col.numeric) {
          const min = Number(raw.replace(/\s/g, "").replace(",", "."));
          if (!Number.isFinite(min)) return true;
          return Number(col.text(row).replace(/\s/g, "").replace(",", ".")) >= min;
        }
        return col.text(row).toLowerCase().includes(raw.trim().toLowerCase());
      }),
    );
  }, [rows, colFilters, columns]);

  const exportColumns: ExportColumn<T>[] = shownCols.map((c) => ({
    key: c.key,
    label: c.label,
    value: (r) => c.text(r),
  }));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-end gap-3">
        {leftMeta ? (
          <div className="mr-auto flex items-center gap-2 text-sm text-ink-600">
            {leftMeta}
          </div>
        ) : null}
        <ColumnsMenu
          columns={columns.map((c) => ({ key: c.key, label: c.label }))}
          visible={visible}
          lockedKeys={columns.filter((c) => c.locked).map((c) => c.key)}
          onToggle={(key) =>
            setVisible((prev) => {
              const next = new Set(prev);
              if (next.has(key)) next.delete(key);
              else next.add(key);
              return next;
            })
          }
        />
        {exportFilename ? (
          <ExportMenu
            filenamePrefix={exportFilename}
            title={exportTitle ?? exportFilename}
            subtitle={exportSubtitle ?? ""}
            columns={exportColumns}
            rows={filtered}
          />
        ) : null}
      </div>

      {rows.length === 0 ? (
        <EmptyState icon={Inbox} title={emptyLabel} tone="neutral" />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line-100 bg-paper shadow-xs">
          <table className="table-admin min-w-full">
            <thead>
              <tr>
                {shownCols.map((c) => (
                  <th key={c.key} className={c.align === "right" ? "text-right" : ""}>
                    {c.label}
                  </th>
                ))}
                {actions ? <th className="text-right">{actionsLabel}</th> : null}
              </tr>
              <tr className="bg-cream/40">
                {shownCols.map((c) => (
                  <th key={c.key} className="py-1.5">
                    {c.filterable === false ? null : (
                      <input
                        value={colFilters[c.key] ?? ""}
                        onChange={(e) =>
                          setColFilters((prev) => ({ ...prev, [c.key]: e.target.value }))
                        }
                        placeholder={c.numeric ? "≥ min" : "filtrer…"}
                        className={
                          "w-full rounded border border-line-200 bg-paper px-2 py-1 text-xs font-normal placeholder:text-ink-300 focus:border-blue-700 focus:outline-none " +
                          (c.align === "right" ? "text-right" : "")
                        }
                      />
                    )}
                  </th>
                ))}
                {actions ? <th /> : null}
              </tr>
            </thead>
            <tbody>
              {filtered.map((row) => (
                <tr key={rowKey(row)}>
                  {shownCols.map((c) => (
                    <td key={c.key} className={c.align === "right" ? "text-right" : ""}>
                      {c.render ? c.render(row) : c.text(row)}
                    </td>
                  ))}
                  {actions ? (
                    <td className="text-right">{actions(row)}</td>
                  ) : null}
                </tr>
              ))}
              {filtered.length === 0 ? (
                <tr>
                  <td
                    colSpan={shownCols.length + (actions ? 1 : 0)}
                    className="py-6 text-center text-sm text-ink-500"
                  >
                    {filteredEmptyLabel}
                  </td>
                </tr>
              ) : null}
            </tbody>
            {showTotals && filtered.length > 0 && shownCols.some((c) => c.numeric) ? (
              <tfoot>
                <tr className="border-t-2 border-line-300 bg-cream/40 font-semibold">
                  {shownCols.map((c, i) => {
                    if (c.numeric) {
                      const total = filtered.reduce(
                        (s, row) =>
                          s + Number(c.text(row).replace(/\s/g, "").replace(",", ".")),
                        0,
                      );
                      return (
                        <td key={c.key} className="text-right tabular-nums text-ink-900">
                          {total.toLocaleString("fr-FR")}
                        </td>
                      );
                    }
                    return (
                      <td key={c.key} className="text-ink-600">
                        {i === 0 ? `Total (${filtered.length})` : ""}
                      </td>
                    );
                  })}
                  {actions ? <td /> : null}
                </tr>
              </tfoot>
            ) : null}
          </table>
        </div>
      )}
    </div>
  );
}
