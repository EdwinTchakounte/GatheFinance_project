"""Scheduled tasks for the savings domain.

Wired by ``apps_coop.audit.management.commands.seed_q_schedules`` to run via
django-q2's qcluster worker.

⚠️ Refonte 2026 — ``crediter_interets_mensuels`` est désormais **désactivé
par défaut** via le kill-switch ``savings.monthly_interest.enabled`` (LOT 3).
Le LOT 4 remplacera ce cron par ``collecte_fin_de_mois`` (commission 1%
prélevée + restitution cash ou bascule épargne) — comportement métier
inverse (la coop prélève au lieu de créditer).

LEGACY 2025 — Le cron ``savings.interest.monthly`` tournait le 1er de chaque
mois à 02h00 :

    pour chaque SavingsAccount où solde >= MIN_BALANCE_FOR_INTEREST :
        si déjà un SavingsTransaction(INTERET) ce mois → skip
        crédit = solde × 0.01           (Article 4 — 1 %/mois)
        solde += crédit  (verrouillé via select_for_update)
        SavingsTransaction(type=INTERET, montant=crédit, payment=None) ← traçabilité
        audit + email
"""
from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit

from .cutoff import MIN_BALANCE_FOR_INTEREST


logger = logging.getLogger(__name__)

_TWO_DP = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


def crediter_interets_mensuels(
    *,
    target_month: "datetime | None" = None,
    force: bool = False,
) -> dict:
    """Crédite le taux d'épargne mensuel sur chaque compte d'épargne actif.

    ⚠️ **LEGACY 2025** — désactivé par défaut depuis la refonte 2026
    (kill-switch ``savings.monthly_interest.enabled``, défaut ``false``).
    Le LOT 4 livrera ``collecte_fin_de_mois`` (commission 1% prélevée vs
    crédit 1% versé) qui prendra le relais ; en attendant, le cron tourne
    à blanc et trace seulement un summary "skipped".

    Arguments :
        target_month: si fourni (ex. ``datetime(2026, 5, 1)``), force la
            période ciblée ET stamppe la SavingsTransaction.date au 1er du mois.
            Permet de rejouer un mois antérieur depuis l'admin (recette).
        force: bypass du kill-switch ``savings.monthly_interest.enabled``.
            À utiliser uniquement via le déclenchement manuel admin.

    Le taux est lu depuis ``RateParam.SAVINGS_INTEREST_MONTHLY`` (modifiable
    côté admin, BR2) avec fallback sur le défaut réglementaire (1 %, Article 4).
    Idempotent : ne crédite pas 2× le même mois pour un compte donné.
    """
    from apps_coop.audit.services import get_str_setting
    from apps_coop.members.models import Member
    from apps_coop.notifications.events import emit_event
    from apps_coop.payments.models import RateParam
    from apps_coop.payments.rates import get_rate
    from apps_coop.savings.models import SavingsAccount, SavingsTransaction

    now = target_month or timezone.now()
    period = f"{now.year}-{now.month:02d}"

    # LOT 3 (refonte 2026) — kill-switch : désactivé par défaut.
    # `force=True` (déclenchement manuel admin) bypass le kill-switch.
    enabled = (
        force
        or get_str_setting("savings.monthly_interest.enabled", "false").lower()
        in {"true", "1", "yes"}
    )
    if not enabled:
        summary = {
            "period": period,
            "skipped_reason": "savings.monthly_interest.enabled=false (refonte 2026)",
        }
        record_audit(
            action="cron.savings_interest.skipped",
            entite_type="cron",
            details=summary,
        )
        logger.info("crediter_interets_mensuels — skipped (refonte 2026)")
        return summary

    taux = get_rate(RateParam.Code.SAVINGS_INTEREST_MONTHLY)

    comptes_traites = 0
    comptes_ignores = 0
    erreurs = 0
    total_credite = Decimal("0")

    # On itère seulement sur les comptes de membres actifs — un compte suspendu
    # n'accumule pas d'épargne dans la logique de la coop.
    qs = (
        SavingsAccount.objects
        .filter(member__statut=Member.Statut.ACTIF)
        .select_related("member", "member__user")
    )

    for account in qs:
        try:
            with transaction.atomic():
                # Verrou ligne — sérialise vis-à-vis des dépôts concurrents.
                locked = (
                    SavingsAccount.objects
                    .select_for_update()
                    .get(pk=account.pk)
                )

                # Idempotence : un seul INTERET par mois calendaire.
                already_credited_this_month = SavingsTransaction.objects.filter(
                    account=locked,
                    type_op=SavingsTransaction.TypeOp.INTERET,
                    date__year=now.year,
                    date__month=now.month,
                ).exists()
                if already_credited_this_month:
                    comptes_ignores += 1
                    continue

                solde = Decimal(locked.solde)
                if solde < MIN_BALANCE_FOR_INTEREST:
                    comptes_ignores += 1
                    continue

                interets = _q(solde * taux)
                if interets <= 0:
                    comptes_ignores += 1
                    continue

                nouveau_solde = _q(solde + interets)
                locked.solde = nouveau_solde
                locked.save(update_fields=["solde", "updated_at"])

                SavingsTransaction.objects.create(
                    account=locked,
                    payment=None,  # crédit système, pas un Payment
                    type_op=SavingsTransaction.TypeOp.INTERET,
                    montant=interets,
                    solde_apres=nouveau_solde,
                    date=now,
                )

                record_audit(
                    action="savings.interest_credited",
                    entite_type="SavingsAccount",
                    entite_id=locked.pk,
                    details={
                        "member_id": locked.member_id,
                        "period": period,
                        "rate": str(taux),
                        "solde_avant": str(solde),
                        "interets": str(interets),
                        "solde_apres": str(nouveau_solde),
                    },
                )

                comptes_traites += 1
                total_credite += interets

            # Email hors transaction — l'échec d'envoi ne doit pas rollback.
            member = account.member
            if getattr(member.user, "email", None):
                try:
                    emit_event(
                        "savings.interest_credited",
                        member=member,
                        context={
                            "prenom": member.prenom,
                            "period": period,
                            "interets": f"{int(interets):,}".replace(",", " "),
                            "solde_apres": f"{int(nouveau_solde):,}".replace(",", " "),
                        },
                    )
                except Exception:  # noqa: BLE001
                    # Le template peut ne pas exister encore — on n'échoue pas le cron.
                    logger.warning("savings.interest_credited email skipped", exc_info=True)

        except Exception:  # noqa: BLE001
            erreurs += 1
            logger.exception(
                "crediter_interets_mensuels — échec sur account_id=%s", account.pk
            )

    summary = {
        "period": period,
        "rate": str(taux),
        "comptes_traites": comptes_traites,
        "comptes_ignores": comptes_ignores,
        "erreurs": erreurs,
        "total_credite": str(total_credite),
    }
    record_audit(
        action="cron.savings_interest.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("crediter_interets_mensuels summary=%s", summary)
    return summary


# ===========================================================================
# LOT 4 (refonte 2026) — Cron mensuel de clôture des collectes
# ===========================================================================


def collecte_fin_de_mois() -> dict:
    """Cron mensuel de clôture des comptes de **collecte journalière** (§4 refonte 2026).

    Pour chaque compte de collecte avec solde > 0 :

      1. **Commission** = solde × ``collecte.monthly.commission_rate`` (défaut 1%)
         → écrit ``SavingsTransaction(COMMISSION, …)`` (revenue coop)
      2. **Restitution** du solde restant selon ``end_of_month_preference`` :
         - ``cash``    → écrit ``SavingsTransaction(RESTITUTION_CASH, …)``
                         + notif au membre « venez récupérer XXX FCFA »
         - ``epargne`` → écrit ``SavingsTransaction(BASCULE_EPARGNE, …)``
                         + ``ClassicSavingsTransaction(DEPOT, …)``
                         + crée ``ClassicSavingsAccount`` à la volée si nécessaire
      3. Solde collecte remis à 0
      4. Event ``collecte.monthly_restitution`` ou ``collecte.balance_swept_to_savings``
         + audit ``cron.collecte_fin_de_mois.run``

    Idempotent : une SEULE commission par compte par mois calendaire (refusé si
    une transaction ``COMMISSION`` existe déjà pour ce ``(account, year, month)``).

    Tunables :
      - ``collecte.monthly.enabled`` (kill-switch, défaut ``true``)
      - ``collecte.monthly.commission_rate`` (défaut ``"0.01"`` = 1 %)

    Wired par ``seed_q_schedules`` (CRON ``0 2 1 * *`` — 1er du mois 02h00).
    """
    from datetime import date

    from apps_coop.audit.services import get_str_setting
    from apps_coop.members.models import Member
    from apps_coop.notifications.events import emit_event
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
        SavingsAccount,
        SavingsTransaction,
    )

    now = timezone.now()
    period = f"{now.year}-{now.month:02d}"

    # Kill-switch (défaut ON pour la nouvelle logique 2026).
    enabled = (
        get_str_setting("collecte.monthly.enabled", "true").lower()
        in {"true", "1", "yes"}
    )
    if not enabled:
        summary = {
            "period": period,
            "skipped_reason": "collecte.monthly.enabled=false",
        }
        record_audit(
            action="cron.collecte_fin_de_mois.skipped",
            entite_type="cron",
            details=summary,
        )
        return summary

    # Taux configurable (AppSetting). Défaut 0.01 = 1 % retenu par la
    # coopérative à la clôture mensuelle (§4 BUSINESS_RULES_2026). L'admin
    # peut le ramener à 0 (restitution intégrale) ou le monter via la page
    # Paramètres 2026 sans redéploiement.
    raw_rate = get_str_setting("collecte.monthly.commission_rate", "0.01")
    try:
        commission_rate = Decimal(str(raw_rate))
    except Exception:  # noqa: BLE001
        commission_rate = Decimal("0.01")

    comptes_traites = 0
    comptes_ignores = 0
    erreurs = 0
    total_commission = Decimal("0")
    total_restitue_cash = Decimal("0")
    total_bascule_epargne = Decimal("0")

    qs = (
        SavingsAccount.objects.filter(member__statut=Member.Statut.ACTIF)
        .select_related("member", "member__user")
    )

    for account in qs:
        try:
            cash_txn = None
            with transaction.atomic():
                locked = (
                    SavingsAccount.objects
                    .select_for_update()
                    .get(pk=account.pk)
                )

                # Idempotence par mois calendaire.
                already_closed = SavingsTransaction.objects.filter(
                    account=locked,
                    type_op=SavingsTransaction.TypeOp.COMMISSION,
                    date__year=now.year,
                    date__month=now.month,
                ).exists()
                if already_closed:
                    comptes_ignores += 1
                    continue

                solde = Decimal(locked.solde)
                if solde <= 0:
                    comptes_ignores += 1
                    continue

                # Étape 1 — commission au profit de la coop.
                commission = _q(solde * commission_rate)
                restituable = _q(solde - commission)

                # On crée d'abord la ligne COMMISSION (solde_apres = restituable).
                SavingsTransaction.objects.create(
                    account=locked,
                    payment=None,
                    type_op=SavingsTransaction.TypeOp.COMMISSION,
                    montant=commission,
                    solde_apres=restituable,
                    date=now,
                )
                total_commission += commission

                # Étape 2 — restitution selon préférence du membre.
                preference = locked.end_of_month_preference
                if preference == SavingsAccount.EndOfMonthPreference.EPARGNE:
                    # Bascule vers l'épargne classique.
                    classic_account, _ = (
                        ClassicSavingsAccount.objects.select_for_update().get_or_create(
                            member=locked.member,
                            defaults={
                                "solde": Decimal("0"),
                                "date_ouverture": date.today(),
                            },
                        )
                    )
                    nouveau_solde_classic = _q(
                        Decimal(classic_account.solde) + restituable
                    )

                    SavingsTransaction.objects.create(
                        account=locked,
                        payment=None,
                        type_op=SavingsTransaction.TypeOp.BASCULE_EPARGNE,
                        montant=restituable,
                        solde_apres=Decimal("0"),
                        date=now,
                    )
                    ClassicSavingsTransaction.objects.create(
                        account=classic_account,
                        payment=None,
                        # Origine explicite : bascule collecte → épargne (vs
                        # un dépôt MoMo générique). Cf. G3 fin de mois 2026.
                        type_op=ClassicSavingsTransaction.TypeOp.BASCULE_COLLECTE,
                        montant=restituable,
                        solde_apres=nouveau_solde_classic,
                        date=now,
                    )
                    classic_account.solde = nouveau_solde_classic
                    classic_account.save(update_fields=["solde", "updated_at"])

                    locked.solde = Decimal("0")
                    locked.save(update_fields=["solde", "updated_at"])
                    total_bascule_epargne += restituable
                    event_code = "collecte.balance_swept_to_savings"
                else:
                    # CASH par défaut.
                    cash_txn = SavingsTransaction.objects.create(
                        account=locked,
                        payment=None,
                        type_op=SavingsTransaction.TypeOp.RESTITUTION_CASH,
                        montant=restituable,
                        solde_apres=Decimal("0"),
                        date=now,
                    )
                    locked.solde = Decimal("0")
                    locked.save(update_fields=["solde", "updated_at"])
                    total_restitue_cash += restituable
                    event_code = "collecte.monthly_restitution"

                record_audit(
                    action="collecte.monthly_closed",
                    entite_type="SavingsAccount",
                    entite_id=locked.pk,
                    details={
                        "period": period,
                        "rate": str(commission_rate),
                        "solde_avant": str(solde),
                        "commission": str(commission),
                        "restituable": str(restituable),
                        "preference": preference,
                    },
                )
                comptes_traites += 1

            # Émission de l'event hors transaction (best-effort).
            member = account.member
            try:
                emit_event(
                    event_code,
                    member=member,
                    context={
                        "prenom": member.prenom,
                        "numero_membre": member.numero_membre,
                        "period": period,
                        "solde_avant": f"{int(solde):,}".replace(",", " "),
                        "commission": f"{int(commission):,}".replace(",", " "),
                        "restituable": f"{int(restituable):,}".replace(",", " "),
                    },
                )
            except Exception:  # noqa: BLE001
                logger.warning("emit_event %s failed", event_code, exc_info=True)

            # Restitution « cash » → décaissement Mobile Money automatique
            # (Tara) si activé via AppSetting. Hors transaction : un échec de
            # payout ne rollback pas la clôture déjà commitée.
            if preference == SavingsAccount.EndOfMonthPreference.CASH:
                try:
                    from apps_coop.savings.services import (
                        initiate_collecte_cash_payout,
                    )

                    initiate_collecte_cash_payout(
                        member, cash_txn, montant=restituable
                    )
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "collecte cash payout échoué (account=%s)",
                        account.pk,
                        exc_info=True,
                    )

        except Exception:  # noqa: BLE001
            erreurs += 1
            logger.exception(
                "collecte_fin_de_mois — échec sur account_id=%s", account.pk
            )

    summary = {
        "period": period,
        "rate": str(commission_rate),
        "comptes_traites": comptes_traites,
        "comptes_ignores": comptes_ignores,
        "erreurs": erreurs,
        "total_commission": str(total_commission),
        "total_restitue_cash": str(total_restitue_cash),
        "total_bascule_epargne": str(total_bascule_epargne),
    }
    record_audit(
        action="cron.collecte_fin_de_mois.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("collecte_fin_de_mois summary=%s", summary)
    return summary


# ===========================================================================
# LOT 5 (refonte 2026) — Cron quotidien anniversaire épargne classique
# ===========================================================================


def epargne_anniversary_processing() -> dict:
    """Cron quotidien — pilote la state machine des comptes d'épargne classique
    autour de leur anniversaire (§5 + §10 refonte 2026).

    Pour chaque ``ClassicSavingsAccount`` non archivé avec
    ``date_prochaine_maturite`` posée :

    | days_until_maturity | Action |
    |---------------------|--------|
    | >= 30               | statut = ACTIF (reset si descendu d'un niveau) |
    | 7..29               | statut = NOTIFIE (+ event ``savings.maturity_30d``) |
    | 1..6                | statut = URGENCE (+ event ``savings.maturity_7d``) |
    | == 0                | **restitution** intégrale + EN_ATTENTE_PAIEMENT |
    | -grace..-1          | reste EN_ATTENTE_PAIEMENT |
    | <= -grace - 1       | statut = ARCHIVE (+ event ``membership.archived_for_non_renewal``) |

    Tunables :
      - ``epargne.contract_months`` (durée du contrat — utilisé par le service)
      - ``epargne.renewal_grace_days`` (défaut 30j)

    Idempotent : restitution effectuée une seule fois par cycle (clé =
    ``cycle_courant``) ; transitions de state machine seulement si elles
    représentent un progrès.
    """

    from apps_coop.audit.services import (
        get_int_setting,
        record as record_audit,
    )
    from apps_coop.notifications.events import emit_event
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
    )

    today = timezone.localdate()
    now = timezone.now()
    grace_days = get_int_setting("epargne.renewal_grace_days", 30)

    Status = ClassicSavingsAccount.StatutRenouvellement

    qs = (
        ClassicSavingsAccount.objects
        .filter(date_prochaine_maturite__isnull=False)
        .exclude(statut_renouvellement=Status.ARCHIVE)
        .select_related("member", "member__user")
    )

    transitions = {key: 0 for key in (
        "actif", "notifie", "urgence", "restitues", "archive", "no_op"
    )}

    for account in qs:
        try:
            with transaction.atomic():
                locked = (
                    ClassicSavingsAccount.objects
                    .select_for_update()
                    .get(pk=account.pk)
                )
                maturite = locked.date_prochaine_maturite
                if maturite is None:
                    transitions["no_op"] += 1
                    continue

                days_until = (maturite - today).days

                if days_until >= 30:
                    new_status = Status.ACTIF
                elif days_until >= 7:
                    new_status = Status.NOTIFIE
                elif days_until >= 1:
                    new_status = Status.URGENCE
                elif days_until == 0 or (
                    days_until < 0 and days_until >= -grace_days
                ):
                    # Restitution déclenchée à J0. Idempotente : si déjà
                    # restituée ce cycle, on saute la création de la ligne.
                    already_restitue = ClassicSavingsTransaction.objects.filter(
                        account=locked,
                        type_op=ClassicSavingsTransaction.TypeOp.RESTITUTION_MATURITE,
                        date__gte=maturite,  # restitution de CE cycle
                    ).exists()
                    if not already_restitue and Decimal(locked.solde) > 0:
                        ancien_solde = Decimal(locked.solde)
                        ClassicSavingsTransaction.objects.create(
                            account=locked,
                            payment=None,
                            type_op=ClassicSavingsTransaction.TypeOp.RESTITUTION_MATURITE,
                            montant=ancien_solde,
                            solde_apres=Decimal("0"),
                            date=now,
                        )
                        locked.solde = Decimal("0")
                        transitions["restitues"] += 1
                        # Event au membre — best-effort.
                        try:
                            emit_event(
                                "savings.maturity_reached",
                                member=locked.member,
                                context={
                                    "prenom": locked.member.prenom,
                                    "numero_membre": locked.member.numero_membre,
                                    "restitution": f"{int(ancien_solde):,}".replace(",", " "),
                                    "grace_days": grace_days,
                                },
                            )
                        except Exception:  # noqa: BLE001
                            logger.warning(
                                "emit_event savings.maturity_reached failed",
                                exc_info=True,
                            )
                    new_status = Status.EN_ATTENTE_PAIEMENT
                else:
                    # days_until < -grace_days → archivage automatique.
                    new_status = Status.ARCHIVE

                # Application + persistance de la transition (si nouvelle).
                if locked.statut_renouvellement != new_status:
                    previous = locked.statut_renouvellement
                    locked.statut_renouvellement = new_status
                    locked.save(
                        update_fields=[
                            "solde",
                            "statut_renouvellement",
                            "updated_at",
                        ]
                    )
                    record_audit(
                        action="savings.statut_renouvellement_changed",
                        entite_type="ClassicSavingsAccount",
                        entite_id=locked.pk,
                        details={
                            "member_id": locked.member_id,
                            "previous": previous,
                            "new": new_status,
                            "days_until_maturity": days_until,
                        },
                    )
                    transitions[new_status] = transitions.get(new_status, 0) + 1

                    if new_status == Status.ARCHIVE:
                        try:
                            emit_event(
                                "membership.archived_for_non_renewal",
                                member=locked.member,
                                context={
                                    "prenom": locked.member.prenom,
                                    "numero_membre": locked.member.numero_membre,
                                },
                            )
                        except Exception:  # noqa: BLE001
                            logger.warning(
                                "emit_event archived_for_non_renewal failed",
                                exc_info=True,
                            )
                else:
                    # On a peut-être quand même touché `solde` (restitution
                    # sans changement de statut — cas EN_ATTENTE_PAIEMENT
                    # qui restait identique mais avec restitution effectuée).
                    if locked.solde != account.solde:
                        locked.save(update_fields=["solde", "updated_at"])
                    transitions["no_op"] += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "epargne_anniversary_processing — échec account_id=%s",
                account.pk,
            )

    summary = {
        "date": today.isoformat(),
        "grace_days": grace_days,
        **transitions,
    }
    record_audit(
        action="cron.epargne_anniversary.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("epargne_anniversary_processing summary=%s", summary)
    return summary


def collecte_eom_choice_reminder() -> dict:
    """Rappel AVANT la clôture mensuelle : notifie chaque membre actif ayant un
    solde de collecte pour qu'il choisisse (cash vs bascule épargne) dans l'app.

    La notification/e-mail utilise le template éditable
    ``collecte.eom_choice_reminder`` (l'admin peut le personnaliser). Sans
    action du membre, le retrait cash reste le comportement par défaut.

    Idempotent-safe : émettre plusieurs fois ne fait qu'ajouter une notif ;
    prévu pour tourner une fois par mois (ex. le 25).
    """
    from datetime import date

    from apps_coop.audit.services import get_str_setting
    from apps_coop.members.models import Member
    from apps_coop.notifications.events import emit_event
    from apps_coop.savings.models import SavingsAccount

    enabled = (
        get_str_setting("collecte.eom_reminder.enabled", "true").lower()
        in ("1", "true", "yes")
    )
    if not enabled:
        return {"skipped": True, "skipped_reason": "collecte.eom_reminder.enabled=false"}

    sent = 0
    accounts = (
        SavingsAccount.objects.select_related("member", "member__user")
        .filter(member__statut=Member.Statut.ACTIF, solde__gt=Decimal("0"))
    )
    for acc in accounts:
        member = acc.member
        if getattr(member, "user", None) is None:
            continue
        emit_event(
            "collecte.eom_choice_reminder",
            member=member,
            context={
                "prenom": member.prenom or member.nom,
                "montant": _q(acc.solde),
            },
        )
        sent += 1

    summary = {"generated_at": date.today().isoformat(), "reminders_sent": sent}
    record_audit(
        action="collecte.eom_choice_reminder.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("collecte_eom_choice_reminder summary=%s", summary)
    return summary


def placement_maturity_processing() -> dict:
    """Cron quotidien : restitue les placements le jour d'échéance configuré.

    Tourne tous les jours mais n'agit que si `today` == la date de restitution
    (AppSetting ``epargne.placement.maturity_date``, MM-DD, défaut 01-01). Cela
    rend la date éditable sans toucher au planning du cron.
    """
    from datetime import date

    from apps_coop.audit.services import get_str_setting

    from .placement_maturity import is_maturity_day, process_placement_maturity

    enabled = (
        get_str_setting("epargne.placement.maturity.enabled", "true").lower()
        in ("1", "true", "yes")
    )
    if not enabled:
        return {"skipped": True, "skipped_reason": "epargne.placement.maturity.enabled=false"}

    today = date.today()
    if not is_maturity_day(today):
        return {"skipped": True, "skipped_reason": "not maturity day"}

    summary = process_placement_maturity(today)
    record_audit(
        action="placement.maturity.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("placement_maturity_processing summary=%s", summary)
    return summary
