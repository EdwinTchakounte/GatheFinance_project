import { Container } from "@gathe/ui";
import { BrandWatermark } from "./brand-watermark";

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
    <section className="relative isolate overflow-hidden bg-midnight py-11 text-white lg:py-14">
      {/* Bande immersive midnight + un seul glow radial par coin (cf. DS :
          filet OU ombre → ici verre + glow). Émeraude en haut-droite,
          cobalt en bas-gauche, très diffus (~90px), tempérés. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-[8%] -top-[35%] h-[34rem] w-[34rem] rounded-full"
        style={{ background: "radial-gradient(circle, rgba(22,163,74,0.22), transparent 65%)", filter: "blur(90px)" }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute bottom-[-35%] -left-[8%] h-[30rem] w-[30rem] rounded-full"
        style={{ background: "radial-gradient(circle, rgba(10,86,171,0.20), transparent 65%)", filter: "blur(90px)" }}
      />
      {/* Filigrane de marque — signature discrète en fond. */}
      <BrandWatermark tone="dark" className="right-[-3%] top-1/2 h-[22rem] w-[22rem] -translate-y-1/2 lg:h-[28rem] lg:w-[28rem]" />

      <Container className="relative">
        <span className="font-display text-[0.72rem] font-semibold uppercase tracking-[0.18em] text-green-300">
          Chiffres clés
        </span>
        <dl className="mt-7 grid grid-cols-2 gap-x-6 gap-y-8 lg:mt-9 lg:grid-cols-4 lg:gap-x-10">
          {figures.map((f, i) => (
            <div
              key={f.label}
              className={`relative ${i > 0 ? "lg:border-l lg:border-white/10 lg:pl-10" : ""}`}
            >
              <span className="font-display text-[0.68rem] font-medium uppercase tracking-[0.14em] text-terra-300/90">
                {`0${i + 1}`}
              </span>
              <p className="mt-2.5 font-display text-[clamp(1.85rem,3vw,2.6rem)] font-semibold leading-none tracking-tight text-white">
                {f.value}
              </p>
              <p className="mt-3 text-[0.74rem] font-medium uppercase tracking-[0.12em] text-white/75">
                {f.label}
              </p>
              <p className="mt-1 text-[0.72rem] leading-snug text-white/45">{f.sub}</p>
            </div>
          ))}
        </dl>
      </Container>
    </section>
  );
}
