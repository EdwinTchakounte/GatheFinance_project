"use client";

import type { ComponentType, SVGProps } from "react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import {
  Building2,
  ChevronDown,
  ChevronRight,
  Facebook,
  Home,
  Linkedin,
  Mail,
  Menu,
  Newspaper,
  UserPlus,
  Wallet,
  X,
} from "lucide-react";

import { buttonClasses, cn, Logo } from "@gathe/ui";
import { Link } from "@/i18n/navigation";
import { siteConfig } from "@/lib/site-config";
import type { NavEntry } from "./nav-menu";
import { LocaleSwitcher } from "./locale-switcher";

type Icon = ComponentType<SVGProps<SVGSVGElement>>;

const NAV_ICONS: Record<string, Icon> = {
  "/": Home,
  "/a-propos": Building2,
  "/services-financiers": Wallet,
  "/blog": Newspaper,
  "/contact": Mail,
};

function iconFor(href: string): Icon | null {
  const base = href.split("#")[0] ?? href;
  return NAV_ICONS[base] ?? null;
}

export function MobileNav({ items, joinLabel, memberLabel }: { items: NavEntry[]; joinLabel: string; memberLabel: string }) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const t = useTranslations("nav");
  const drawerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const close = () => {
    setOpen(false);
    setExpanded(null);
  };

  // A11y : quand le drawer est ouvert, on déplace le focus dedans, on piège Tab
  // à l'intérieur (focus-trap), on ferme sur Échap, et on restitue le focus au
  // bouton burger à la fermeture.
  useEffect(() => {
    if (!open) return;
    const trigger = triggerRef.current; // capturé tôt pour le cleanup (nœud stable)
    const focusables = () =>
      drawerRef.current
        ? Array.from(
            drawerRef.current.querySelectorAll<HTMLElement>(
              'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])',
            ),
          ).filter((el) => el.offsetParent !== null)
        : [];

    focusables()[0]?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
        return;
      }
      if (e.key !== "Tab") return;
      const f = focusables();
      if (f.length === 0) return;
      const first = f[0]!;
      const last = f[f.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      trigger?.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const drawer = open ? (
    <div
      ref={drawerRef}
      id="mobile-nav-drawer"
      role="dialog"
      aria-modal="true"
      aria-label="Menu"
      className="fixed inset-0 z-[60] flex flex-col bg-paper lg:hidden"
    >
      {/* ===== Drawer header — brand + close ===== */}
      <div className="flex h-16 items-center justify-between border-b border-line-200 bg-surface-50 px-5">
        <Link href="/" onClick={close} aria-label={siteConfig.name} className="inline-flex">
          <Logo className="h-8 w-auto" />
        </Link>
        <button
          type="button"
          aria-label={t("closeMenu")}
          onClick={close}
          className="inline-flex size-10 items-center justify-center rounded-full text-ink-700 transition-colors hover:bg-cream hover:text-blue-700"
        >
          <X aria-hidden="true" className="size-5" />
        </button>
      </div>

      {/* ===== Scrollable body ===== */}
      <div className="flex-1 overflow-y-auto">
        {/* Top-level items */}
        <nav aria-label="Navigation mobile" className="px-3 pt-4">
          <ul className="flex flex-col gap-0.5">
            {items.map((item) => {
              const ItemIcon = iconFor(item.href);
              const isExpanded = expanded === item.href;
              const hasChildren = !!item.children?.length;

              return (
                <li key={item.href} className="relative">
                  {hasChildren ? (
                    <>
                      <button
                        type="button"
                        onClick={() => setExpanded((e) => (e === item.href ? null : item.href))}
                        aria-expanded={isExpanded}
                        className={cn(
                          "group/itm flex w-full items-center gap-3 rounded-md px-3 py-3.5 text-left text-[0.95rem] font-medium text-ink-900",
                          "transition-colors hover:bg-cream",
                          isExpanded && "bg-cream",
                        )}
                      >
                        {ItemIcon ? (
                          <ItemIcon
                            aria-hidden="true"
                            className={cn(
                              "size-[18px] shrink-0 text-ink-400 transition-colors",
                              "group-hover/itm:text-emerald",
                              isExpanded && "text-emerald",
                            )}
                          />
                        ) : null}
                        <span className="flex-1">{item.label}</span>
                        <ChevronDown
                          aria-hidden="true"
                          className={cn(
                            "size-4 shrink-0 text-ink-400 transition-transform duration-300",
                            isExpanded && "rotate-180 text-emerald",
                          )}
                        />
                      </button>

                      {/* Submenu */}
                      <div
                        className={cn(
                          "grid transition-[grid-template-rows] duration-300 ease-out",
                          isExpanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
                        )}
                      >
                        <div className="overflow-hidden">
                          <ul className="ml-[34px] mt-1 flex flex-col gap-0.5 border-l border-line-200 pl-3">
                            <li>
                              <Link
                                href={item.href}
                                onClick={close}
                                className="group/sub flex items-center justify-between rounded-md px-3 py-2 text-[0.85rem] font-medium text-blue-700 transition-colors hover:bg-cream"
                              >
                                <span>{item.label}</span>
                                <ChevronRight aria-hidden="true" className="size-3.5 opacity-0 transition-opacity group-hover/sub:opacity-100" />
                              </Link>
                            </li>
                            {item.children!.map((c) => (
                              <li key={c.href}>
                                <Link
                                  href={c.href}
                                  onClick={close}
                                  className="group/sub flex items-center justify-between rounded-md px-3 py-2 text-[0.85rem] text-ink-600 transition-colors hover:bg-cream hover:text-blue-700"
                                >
                                  <span>{c.label}</span>
                                  <ChevronRight aria-hidden="true" className="size-3.5 opacity-0 transition-opacity group-hover/sub:opacity-100" />
                                </Link>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </>
                  ) : (
                    <Link
                      href={item.href}
                      onClick={close}
                      className="group/itm flex items-center gap-3 rounded-md px-3 py-3.5 text-[0.95rem] font-medium text-ink-900 transition-colors hover:bg-cream"
                    >
                      {ItemIcon ? (
                        <ItemIcon
                          aria-hidden="true"
                          className="size-[18px] shrink-0 text-ink-400 transition-colors group-hover/itm:text-emerald"
                        />
                      ) : null}
                      <span className="flex-1">{item.label}</span>
                      <ChevronRight
                        aria-hidden="true"
                        className="size-3.5 shrink-0 text-ink-300 opacity-0 transition-opacity group-hover/itm:opacity-100"
                      />
                    </Link>
                  )}
                </li>
              );
            })}

            {/* Member space — portail membre séparé (apps/portal) → URL absolue. */}
            <li className="mt-1 border-t border-line-200 pt-2">
              <a
                href={`${process.env.NEXT_PUBLIC_PORTAL_URL ?? "http://localhost:3201"}/connexion`}
                onClick={close}
                className="group/itm flex items-center gap-3 rounded-md px-3 py-3 text-[0.9rem] text-ink-700 transition-colors hover:bg-cream hover:text-blue-700"
              >
                <UserPlus aria-hidden="true" className="size-[18px] shrink-0 text-ink-400 group-hover/itm:text-emerald" />
                <span className="flex-1">{memberLabel}</span>
              </a>
            </li>
          </ul>
        </nav>

        {/* ===== Primary CTA ===== */}
        <div className="border-t border-line-200 px-5 py-5">
          <Link
            href="/devenir-membre"
            onClick={close}
            className={cn(buttonClasses({ variant: "success", size: "lg", fullWidth: true }))}
          >
            {joinLabel}
          </Link>
        </div>

        {/* ===== Locale + social + contact ===== */}
        <div className="space-y-5 border-t border-line-200 px-5 py-6">
          <div className="flex items-center justify-between gap-4">
            <LocaleSwitcher />
            <div className="flex items-center gap-2">
              <a
                href={siteConfig.social.facebook}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Facebook"
                className="inline-flex size-11 items-center justify-center rounded-full border border-line-200 text-ink-600 transition-colors hover:border-blue-700 hover:text-blue-700"
              >
                <Facebook aria-hidden="true" className="size-3.5" />
              </a>
              <a
                href={siteConfig.social.linkedin}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="LinkedIn"
                className="inline-flex size-11 items-center justify-center rounded-full border border-line-200 text-ink-600 transition-colors hover:border-blue-700 hover:text-blue-700"
              >
                <Linkedin aria-hidden="true" className="size-4" />
              </a>
            </div>
          </div>

          <div className="space-y-1.5 border-t border-line-200 pt-4 text-[0.85rem] leading-relaxed text-ink-500">
            <p>{siteConfig.contact.address}</p>
            <p>
              <a className="text-ink-700 hover:text-blue-700" href={siteConfig.contact.phoneHref}>
                {siteConfig.contact.phone}
              </a>
            </p>
            <p>
              <a className="text-ink-700 hover:text-blue-700" href={siteConfig.contact.emailHref}>
                {siteConfig.contact.email}
              </a>
            </p>
            <p className="text-ink-400">{siteConfig.contact.openingHours}</p>
          </div>
        </div>
      </div>
    </div>
  ) : null;

  return (
    <div className="lg:hidden">
      <button
        ref={triggerRef}
        type="button"
        aria-label={open ? t("closeMenu") : t("openMenu")}
        aria-expanded={open}
        aria-controls="mobile-nav-drawer"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex size-10 items-center justify-center rounded-full text-ink-700 transition-colors hover:bg-cream hover:text-blue-700"
      >
        {open ? <X aria-hidden="true" className="size-5" /> : <Menu aria-hidden="true" className="size-5" />}
      </button>

      {mounted && drawer ? createPortal(drawer, document.body) : null}
    </div>
  );
}
