"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { X } from "lucide-react";

import { Container, buttonClasses, cn } from "@gathe/ui";
import { Link } from "@/i18n/navigation";

const STORAGE_KEY = "gathe-cookie-consent";

/** Lightweight cookie-consent bar. Stores the choice in localStorage; only "accept" enables analytics later. */
export function CookieBanner() {
  const t = useTranslations("cookies");
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setVisible(true);
    } catch {
      /* localStorage unavailable — don't show */
    }
  }, []);

  function decide(choice: "accepted" | "declined") {
    try {
      localStorage.setItem(STORAGE_KEY, choice);
    } catch {
      /* ignore */
    }
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 px-3 pb-3 sm:px-4 sm:pb-4">
      <Container className="!px-0">
        <div className="relative flex flex-col gap-4 rounded-2xl border border-line-200 bg-surface-50 p-5 shadow-[var(--shadow-lg)] sm:flex-row sm:items-center sm:gap-6 sm:p-6">
          <p className="flex-1 text-sm leading-relaxed text-ink-600">
            {t("text")}{" "}
            <Link href="/politique-confidentialite" className="font-medium text-blue-700 underline underline-offset-2 hover:text-blue-800">
              {t("link")}
            </Link>
            .
          </p>
          <div className="flex shrink-0 items-center gap-2">
            <button type="button" onClick={() => decide("declined")} className={cn(buttonClasses({ variant: "secondary", size: "sm" }))}>
              {t("decline")}
            </button>
            <button type="button" onClick={() => decide("accepted")} className={cn(buttonClasses({ size: "sm" }))}>
              {t("accept")}
            </button>
          </div>
          <button
            type="button"
            aria-label={t("decline")}
            onClick={() => decide("declined")}
            className="absolute right-2 top-2 inline-flex size-9 items-center justify-center rounded-full text-ink-500 hover:bg-ink-100 hover:text-ink-700 sm:hidden"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
      </Container>
    </div>
  );
}
