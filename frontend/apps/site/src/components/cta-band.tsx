import { getTranslations } from "next-intl/server";
import { ArrowRight } from "lucide-react";

import { buttonClasses, Container } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { InstitutionalDecor } from "./institutional-decor";
import { BrandWatermark } from "./brand-watermark";
import { Reveal } from "./reveal";

/** Recurring "Join the cooperative" CTA — calm editorial band on cream paper.
 *  No background decoration: the eyebrow, the serif headline, the lead and
 *  the two CTAs do all the work. Hairlines at top + bottom anchor it as a
 *  proper press section. */
export async function CtaBand() {
  const t = await getTranslations("home.cta");
  const tn = await getTranslations("nav");

  return (
    <section className="relative isolate overflow-hidden bg-paper py-24 text-ink-900 sm:py-28">
      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-line-200" />
      <div aria-hidden="true" className="absolute inset-x-0 bottom-0 h-px bg-line-200" />

      <InstitutionalDecor variant="flow" />
      {/* Filigrane de marque centré, très discret, derrière le message. */}
      <BrandWatermark tone="light" className="left-1/2 top-1/2 h-[26rem] w-[26rem] -translate-x-1/2 -translate-y-1/2 lg:h-[34rem] lg:w-[34rem]" />

      <Container className="relative">
        <Reveal className="mx-auto text-center">
          <span className="label-num mx-auto">{tn("memberSpace")}</span>

          <h2 className="mx-auto mt-7 max-w-3xl text-balance font-editorial text-[clamp(1.875rem,3.2vw,2.875rem)] font-medium leading-[1.18] text-ink-900">
            {t("title")}
          </h2>

          <p className="mx-auto mt-8 max-w-[72ch] text-pretty text-[1.0625rem] leading-[1.7] text-ink-700 lg:max-w-[96ch] lg:text-[1.05rem] xl:max-w-[108ch]">
            {t("text")}
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link href="/devenir-membre" className={buttonClasses({ variant: "success", size: "lg" })}>
              {t("button")} <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
            <Link href="/contact" className={buttonClasses({ variant: "secondary", size: "lg" })}>
              {tn("contact")}
            </Link>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
