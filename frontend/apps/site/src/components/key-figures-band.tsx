import { Container } from "@gathe/ui";

/**
 * Bandeau "Chiffres-clés" — 4 valeurs tirées exclusivement du Règlement
 * Intérieur GATHE Finance 2025 (déjà câblées dans `apps_coop/loans/terms.py`
 * et `apps_coop/savings/...`). Aucun chiffre n'est inventé.
 *
 * Style éditorial press : eyebrow numéroté terra, grande valeur Syne,
 * label majuscule, sous-label discret avec référence à l'article. Bandeau
 * cream avec hairlines top/bottom, responsive (2 cols mobile → 4 cols lg).
 */
type Figure = { value: string; label: string; sub: string };

const DEFAULT_FIGURES: Figure[] = [
  { value: "10 %", label: "Taux crédit", sub: "Article 5 — par transaction" },
  { value: "8", label: "Paliers de durée", sub: "Article 7 — de 2 à 9 mois" },
  { value: "1 000 F", label: "Collecte journalière", sub: "Article 4 — cut-off 17 h" },
  { value: "1 % / mois", label: "Intérêts épargne", sub: "Article 4 — capitalisés" },
];

export function KeyFiguresBand({ figures = DEFAULT_FIGURES }: { figures?: Figure[] }) {
  return (
    <section className="border-y border-line-200 bg-cream py-12 lg:py-16">
      <Container>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-10 lg:grid-cols-4 lg:gap-x-8">
          {figures.map((f, i) => (
            <div
              key={f.label}
              className={`relative ${i > 0 ? "lg:border-l lg:border-line-200 lg:pl-8" : ""}`}
            >
              <span className="font-display text-[0.7rem] font-medium uppercase tracking-[0.14em] text-terra-600">
                {`0${i + 1}`}
              </span>
              <p className="mt-3 font-editorial text-[clamp(1.75rem,3.2vw,2.75rem)] font-medium leading-none text-ink-900">
                {f.value}
              </p>
              <p className="mt-3 text-[0.78rem] font-medium uppercase tracking-[0.12em] text-ink-700">
                {f.label}
              </p>
              <p className="mt-1 text-xs leading-snug text-ink-500">{f.sub}</p>
            </div>
          ))}
        </dl>
      </Container>
    </section>
  );
}
