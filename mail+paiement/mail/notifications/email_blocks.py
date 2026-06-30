"""Réutilisable email building blocks - style inline pour compat inbox.

Chaque helper retourne un fragment HTML prêt à concaténer dans le
``corps_html`` d'un EmailTemplate. Les placeholders de variables
(``{prenom}``, ``{montant}``…) sont injectés tels quels par
``send_template`` via ``str.format(**context)``.

Design system aligné avec la vitrine Gathe Finance :
- Typographie sans-serif système + serif Georgia pour les titres
- Palette navy #1E3A8A, teal #00B894, bleu accent #0EA5E9
- Cards info à fond bleu pâle, CTA pill bleu navy

NOTE - Le wrapper visuel (header aurore + footer + logo) vient de
``services._wrap_layout`` au moment de l'envoi. Ici, on ne produit que
le corps central.
"""
from __future__ import annotations


# ── Couleurs (alignées sur le brand) ──────────────────────────────────────
NAVY = "#1E3A8A"
NAVY_DEEP = "#1E40AF"
TEAL = "#00B894"
BLUE = "#0EA5E9"
INK = "#0F172A"
INK_SOFT = "#374151"
INK_MUTED = "#6B7280"
LINE = "#E5E7EB"
PAPER = "#FFFFFF"
INFO_BG = "#F0F9FF"
INFO_BORDER = "#BAE6FD"
INFO_LABEL = "#0369A1"
SUCCESS_BG = "#ECFDF5"
SUCCESS_BORDER = "#A7F3D0"
SUCCESS_LABEL = "#047857"
WARN_BG = "#FEF3C7"
WARN_BORDER = "#FDE68A"
WARN_LABEL = "#92400E"
DANGER_BG = "#FEE2E2"
DANGER_BORDER = "#FECACA"
DANGER_LABEL = "#B91C1C"


# ── Building blocks ──────────────────────────────────────────────────────


def title(text: str) -> str:
    """Titre principal du corps (sous le header aurore)."""
    return (
        f'<h1 style="margin:0 0 16px 0;font-family:Georgia,\'Times New Roman\',serif;'
        f'font-size:24px;font-weight:600;color:{INK};line-height:1.25;">{text}</h1>'
    )


def hi(name_placeholder: str = "{prenom}") -> str:
    """Salutation simple : ``Bonjour <strong>NAME</strong>,``."""
    return (
        f'<p style="margin:0 0 14px 0;color:{INK};font-size:16px;line-height:1.55;">'
        f'Bonjour <strong>{name_placeholder}</strong>,</p>'
    )


def lead(text: str) -> str:
    """Paragraphe principal en gras visuel (lead)."""
    return (
        f'<p style="margin:0 0 20px 0;color:{INK_SOFT};font-size:15px;line-height:1.7;">'
        f'{text}</p>'
    )


def p(text: str) -> str:
    """Paragraphe standard."""
    return (
        f'<p style="margin:0 0 16px 0;color:{INK_SOFT};font-size:14.5px;line-height:1.7;">'
        f'{text}</p>'
    )


def amount(value_placeholder: str, label: str = "Montant") -> str:
    """Bloc montant proéminent - pour les emails de confirmation paiement."""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:18px 0 22px 0;">'
        f'<tr><td align="center" style="padding:20px 24px;background:{INFO_BG};'
        f'border:1px solid {INFO_BORDER};border-radius:14px;">'
        f'<div style="color:{INFO_LABEL};font-size:11px;font-weight:600;letter-spacing:0.12em;'
        f'text-transform:uppercase;margin-bottom:6px;">{label}</div>'
        f'<div style="color:{NAVY};font-family:Georgia,serif;font-size:30px;font-weight:600;'
        f'letter-spacing:-0.5px;">{value_placeholder} <span style="font-size:14px;'
        f'color:{INK_MUTED};font-weight:500;font-family:Helvetica,sans-serif;">XAF</span></div>'
        f'</td></tr></table>'
    )


def info_card(rows: list[tuple[str, str]], tone: str = "info") -> str:
    """Carte de détails (table 2 colonnes label → valeur).

    ``tone`` ∈ {"info", "success", "warn", "danger"} : pilote la couleur
    de fond et du label.
    """
    palette = {
        "info": (INFO_BG, INFO_BORDER, INFO_LABEL),
        "success": (SUCCESS_BG, SUCCESS_BORDER, SUCCESS_LABEL),
        "warn": (WARN_BG, WARN_BORDER, WARN_LABEL),
        "danger": (DANGER_BG, DANGER_BORDER, DANGER_LABEL),
    }.get(tone, (INFO_BG, INFO_BORDER, INFO_LABEL))
    bg, border, label_col = palette
    rows_html = "".join(
        f'<tr>'
        f'<td style="padding:8px 0;color:{label_col};font-size:12px;font-weight:600;'
        f'letter-spacing:0.04em;width:46%;vertical-align:top;">{label}</td>'
        f'<td style="padding:8px 0;color:{INK};font-size:14px;font-weight:500;'
        f'text-align:right;">{value}</td>'
        f'</tr>'
        for label, value in rows
    )
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:18px 0 22px 0;background:{bg};border:1px solid {border};'
        f'border-radius:14px;">'
        f'<tr><td style="padding:20px 24px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'{rows_html}</table>'
        f'</td></tr></table>'
    )


def cta(text: str, url_placeholder: str) -> str:
    """Bouton CTA pill, centré, gradient bleu→navy."""
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" '
        f'style="margin:24px auto;">'
        f'<tr><td align="center" style="background-color:{NAVY};'
        f'background-image:linear-gradient(135deg,{NAVY_DEEP} 0%,{NAVY} 100%);'
        f'border-radius:10px;box-shadow:0 4px 14px rgba(30,58,138,0.25);">'
        f'<a href="{url_placeholder}" '
        f'style="display:inline-block;padding:14px 30px;color:#FFFFFF;font-size:14px;'
        f'font-weight:600;text-decoration:none;letter-spacing:0.02em;">'
        f'{text} →</a>'
        f'</td></tr></table>'
    )


def cta_secondary(text: str, url_placeholder: str) -> str:
    """Bouton CTA secondaire - outline (pour cas alternatif)."""
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" '
        f'style="margin:24px auto;">'
        f'<tr><td align="center" style="border:1.5px solid {NAVY};border-radius:10px;'
        f'background:#FFFFFF;">'
        f'<a href="{url_placeholder}" '
        f'style="display:inline-block;padding:12px 28px;color:{NAVY};font-size:14px;'
        f'font-weight:600;text-decoration:none;letter-spacing:0.02em;">'
        f'{text}</a>'
        f'</td></tr></table>'
    )


def callout(text: str, tone: str = "info") -> str:
    """Bloc de mise en garde / info importante."""
    palette = {
        "info": (INFO_BG, INFO_BORDER, INFO_LABEL),
        "success": (SUCCESS_BG, SUCCESS_BORDER, SUCCESS_LABEL),
        "warn": (WARN_BG, WARN_BORDER, WARN_LABEL),
        "danger": (DANGER_BG, DANGER_BORDER, DANGER_LABEL),
    }.get(tone, (INFO_BG, INFO_BORDER, INFO_LABEL))
    bg, border, label_col = palette
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:14px 0 20px 0;background:{bg};border-left:4px solid {label_col};'
        f'border-radius:8px;">'
        f'<tr><td style="padding:14px 18px;color:{INK_SOFT};font-size:14px;line-height:1.6;">'
        f'{text}</td></tr></table>'
    )


def code_block(value_placeholder: str, label: str = "Votre code") -> str:
    """Code OTP en gros caractères monospace - pour les reset PWD."""
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin:22px 0;">'
        f'<tr><td align="center" style="padding:22px 16px;background:{INFO_BG};'
        f'border:1px solid {INFO_BORDER};border-radius:14px;">'
        f'<div style="color:{INFO_LABEL};font-size:11px;font-weight:600;letter-spacing:0.14em;'
        f'text-transform:uppercase;margin-bottom:8px;">{label}</div>'
        f'<div style="color:{NAVY};font-family:\'Courier New\',monospace;font-size:36px;'
        f'font-weight:700;letter-spacing:14px;padding-left:14px;">{value_placeholder}</div>'
        f'</td></tr></table>'
    )


def closing() -> str:
    """Pied de message - signature équipe + contact discret."""
    return (
        f'<p style="margin:28px 0 4px 0;color:{INK_MUTED};font-size:13px;line-height:1.6;">'
        f'Une question ? Écris-nous à '
        f'<a href="mailto:contact@gathe-finance.com" style="color:{NAVY};text-decoration:none;'
        f'font-weight:500;">contact@gathe-finance.com</a>.</p>'
        f'<p style="margin:6px 0 0 0;color:{INK};font-size:14px;font-weight:600;">'
        f'- L\'équipe Gathe Finance</p>'
    )
