"""Service-layer functions for the loans domain.

Pure business logic — no HTTP, no admin templates.
Each public function is atomic + idempotent.
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit
from apps_coop.members.models import Member
from apps_coop.payments.models import RateParam
from apps_coop.payments.rates import get_rate
from apps_coop.savings.models import SavingsAccount

from .models import Loan, LoanInstallment, LoanRenewal, LoanRequest
from .terms import (
    PaymentModality,
    duration_months_for,
    n_installments,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Eligibility — read-only check used by the portal
# ---------------------------------------------------------------------------


@dataclass
class Eligibility:
    eligible: bool
    plafond_max: Decimal
    motifs: list[str]
    # Useful context for the UI to display the rules to the member.
    solde_epargne: Decimal
    ratio_garantie: Decimal


# Configurable thresholds — to move to ``AppSetting`` once we wire the admin tools.
PLAFOND_PAR_RAPPORT_AU_SOLDE = Decimal("10.0")  # plafond = solde × 10
ANCIENNETE_MIN_MOIS = 0  # MVP: no anciennity requirement


def compute_eligibility(member: Member) -> Eligibility:
    """Return whether a member can submit a new credit request, plus context.

    Rules (MVP) :
      1. ``Member.statut == actif``
      2. No `Loan` in statut `actif` / `en_retard` / `contentieux`
      3. No `LoanRequest` already in `en_attente` / `en_instruction` /
         `en_attente_acceptation_membre`
      4. ``solde_epargne >= 100 XAF`` (minimum to allow a request at all)
      5. ``plafond_max = solde_epargne × 10`` (capped by AppSetting later)
    """
    motifs: list[str] = []

    # Rule 1
    if member.statut != Member.Statut.ACTIF:
        motifs.append("Compte membre non actif.")

    # Rule 2
    active_loans = Loan.objects.filter(
        member=member,
        statut__in=[Loan.Statut.ACTIF, Loan.Statut.EN_RETARD, Loan.Statut.CONTENTIEUX],
    ).count()
    if active_loans:
        motifs.append(
            f"Tu as déjà {active_loans} crédit(s) actif(s) ou en cours. "
            "Termine-les avant d'en demander un nouveau."
        )

    # Rule 3
    pending_requests = LoanRequest.objects.filter(
        member=member,
        statut__in=[
            LoanRequest.Statut.EN_ATTENTE,
            LoanRequest.Statut.EN_INSTRUCTION,
            LoanRequest.Statut.EN_ATTENTE_ACCEPTATION_MEMBRE,
        ],
    ).count()
    if pending_requests:
        motifs.append(
            "Tu as déjà une demande en cours. "
            "Attends la décision avant d'en soumettre une nouvelle."
        )

    # Rule 4 + plafond
    try:
        solde = member.savings_account.solde
    except SavingsAccount.DoesNotExist:
        solde = Decimal("0")
    if solde < Decimal("100"):
        motifs.append("Solde d'épargne insuffisant (minimum 100 XAF).")

    plafond_max = (solde * PLAFOND_PAR_RAPPORT_AU_SOLDE).quantize(Decimal("1"))

    return Eligibility(
        eligible=len(motifs) == 0,
        plafond_max=plafond_max,
        motifs=motifs,
        solde_epargne=solde,
        ratio_garantie=PLAFOND_PAR_RAPPORT_AU_SOLDE,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TWO_DP = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


def _add_months(d: date, n: int) -> date:
    """Return ``d + n months``, clamping the day to the new month's last day."""
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _next_installment_date(start: date, index_zero_based: int, modalite: str) -> date:
    """Date de l'échéance ``i`` (0-based) selon la modalité.

    - ``mensuel``       : start + i mois
    - ``hebdomadaire``  : start + i × 7 jours
    - ``journalier``    : start + i jours
    """
    from datetime import timedelta
    if modalite == PaymentModality.MENSUEL:
        return _add_months(start, index_zero_based)
    if modalite == PaymentModality.HEBDOMADAIRE:
        return start + timedelta(days=7 * index_zero_based)
    if modalite == PaymentModality.JOURNALIER:
        return start + timedelta(days=index_zero_based)
    raise ValueError(f"Modalité inconnue : {modalite!r}")


def _next_numero_dossier() -> str:
    """Sequential ``GF-CR-YYYY-NNNN``."""
    year = timezone.now().year
    prefix = f"GF-CR-{year}-"
    max_seq = 0
    for n in Loan.objects.filter(numero_dossier__startswith=prefix).values_list("numero_dossier", flat=True):
        try:
            max_seq = max(max_seq, int(n.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return f"{prefix}{max_seq + 1:04d}"


# ---------------------------------------------------------------------------
# Schedule generation — flat 10 % interest (Règlement, Article 5)
# ---------------------------------------------------------------------------


def generate_installments_flat_interest(
    loan: Loan, *, interets_totaux: Decimal | None = None
) -> list[LoanInstallment]:
    """Génère l'échéancier d'un Loan selon le règlement.

    Règlement Intérieur, Article 5 :
        Un taux d'intérêt de **10 % est appliqué par transaction**.

    Ce n'est donc pas un taux annuel composé : c'est une majoration plate sur
    le capital, payée en plus du capital sur la durée du crédit. La fonction
    répartit également capital et intérêts entre toutes les échéances :

        intérêts_totaux = montant × taux            (10 % par défaut)
        n               = durée_mois × cadence(modalité)
        capital_par_éch = montant / n
        intérêts_par_éch = intérêts_totaux / n
        mensualité      = capital_par_éch + intérêts_par_éch

    La dernière échéance absorbe le reliquat d'arrondi pour que la somme des
    capitaux soit exactement ``montant`` (idem pour les intérêts).

    ``interets_totaux`` (optionnel) : pour une **reconduction**, les intérêts
    ne se calculent pas sur ``montant`` mais sur le **capital restant**
    (Article 11). On passe alors le montant d'intérêts déjà calculé ; sinon
    (crédit initial) on retombe sur ``montant × taux``.

    L'historique conservait l'ancien nom ``generate_installments_amortissement_constant``
    par compat ; il pointe désormais sur cette fonction (alias en bas du module).
    """
    n = n_installments(loan.duree_mois, loan.modalite_paiement)
    montant = Decimal(loan.montant)
    if interets_totaux is None:
        taux = Decimal(loan.taux_interet)
        interets_totaux = _q(montant * taux)
    else:
        interets_totaux = _q(Decimal(interets_totaux))
    capital_par_ech = _q(montant / n)
    interets_par_ech = _q(interets_totaux / n)

    installments: list[LoanInstallment] = []
    capital_distribue = Decimal("0")
    interets_distribues = Decimal("0")
    for i in range(1, n + 1):
        if i == n:
            # Dernière échéance : absorbe le reliquat d'arrondi.
            capital = _q(montant - capital_distribue)
            interets = _q(interets_totaux - interets_distribues)
        else:
            capital = capital_par_ech
            interets = interets_par_ech
        montant_total = _q(capital + interets)
        inst = LoanInstallment.objects.create(
            loan=loan,
            numero_echeance=i,
            date_echeance=_next_installment_date(
                loan.date_premiere_echeance, i - 1, loan.modalite_paiement
            ),
            montant_capital=capital,
            montant_interets=interets,
            montant_total=montant_total,
            statut=LoanInstallment.Statut.A_VENIR,
        )
        installments.append(inst)
        capital_distribue += capital
        interets_distribues += interets
    return installments


#: Alias rétro-compat. Anciens appels ``generate_installments_amortissement_constant``
#: continuent de fonctionner — la signature est identique (1 paramètre : ``loan``).
generate_installments_amortissement_constant = generate_installments_flat_interest


def _remaining_capital_and_interest(loan: Loan) -> tuple[Decimal, Decimal]:
    """Capital et intérêts encore dus sur ``loan``, échéance par échéance.

    Au sein d'une échéance, le versement (``montant_paye``) couvre d'abord le
    capital+intérêts (``montant_total``) ; l'éventuelle pénalité se règle en
    plus. On proratise donc le reste dû sur la part capital+intérêts :

        payé_ci   = min(montant_paye, montant_total)
        reste_ratio = (montant_total − payé_ci) / montant_total
        capital_restant  += montant_capital  × reste_ratio
        intérêts_restants += montant_interets × reste_ratio

    Les pénalités ne sont volontairement **pas** reprises dans la base de
    reconduction (la formule validée = capital + intérêts + taux×capital).
    """
    capital_restant = Decimal("0")
    interets_restants = Decimal("0")
    for inst in loan.installments.all():
        total = Decimal(inst.montant_total)
        if total <= 0:
            continue
        paye_ci = min(Decimal(inst.montant_paye), total)
        reste_ratio = (total - paye_ci) / total
        capital_restant += Decimal(inst.montant_capital) * reste_ratio
        interets_restants += Decimal(inst.montant_interets) * reste_ratio
    return _q(capital_restant), _q(interets_restants)


# ---------------------------------------------------------------------------
# Approve / reject — public API used by Django admin actions
# ---------------------------------------------------------------------------


@transaction.atomic
def approve_loan_request(
    loan_request: LoanRequest,
    *,
    decided_by,
    taux_annuel: Decimal | None = None,
    date_premiere_echeance: date,
    date_comite: date | None = None,
    pv_comite=None,
) -> Loan:
    """Create the Loan + the full installment schedule atomically.

    Règlement Intérieur appliqué :
      - Taux : ``RateParam.LOAN_INTEREST`` (défaut 10 % par transaction,
        Article 5, modifiable côté admin) ; ``taux_annuel`` reste accepté pour
        rétro-compat (admin Django) — sa valeur écrase le taux courant si fournie.
      - Durée : dérivée du ``montant_demande`` via le tableau de paliers
        (Article 7). La valeur stockée dans ``LoanRequest.duree_mois`` est
        ignorée pour éviter toute incohérence avec le règlement.
      - Modalité : propagée depuis la demande (Article 8).

    Idempotent : si la demande est déjà ``approuvee``, renvoie le Loan existant.
    """
    if loan_request.statut == LoanRequest.Statut.APPROUVEE:
        return loan_request.loan
    if loan_request.statut != LoanRequest.Statut.EN_INSTRUCTION:
        raise ValueError(
            f"Cannot approve a request with status {loan_request.statut!r} "
            f"(expected {LoanRequest.Statut.EN_INSTRUCTION!r})."
        )

    taux = (
        Decimal(taux_annuel)
        if taux_annuel is not None
        else get_rate(RateParam.Code.LOAN_INTEREST)
    )
    montant = Decimal(loan_request.montant_demande)
    duree = duration_months_for(montant)
    modalite = loan_request.modalite_paiement or PaymentModality.MENSUEL

    # Flat interest (Article 5) : intérêts_totaux = montant × taux.
    montant_total_du = _q(montant + (montant * taux))

    # EXT-versioning : on FIGE le taux de pénalité au décaissement (le membre
    # signe un contrat avec ce taux — un changement admin ultérieur ne doit
    # pas s'appliquer rétroactivement).
    taux_penalite_fige = get_rate(RateParam.Code.LATE_PENALTY)

    loan = Loan.objects.create(
        loan_request=loan_request,
        member=loan_request.member,
        numero_dossier=_next_numero_dossier(),
        montant=montant,
        taux_interet=taux,
        taux_penalite=taux_penalite_fige,
        duree_mois=duree,
        modalite_paiement=modalite,
        date_decaissement=timezone.localdate(),
        date_premiere_echeance=date_premiere_echeance,
        montant_total_du=montant_total_du,
        solde_restant=montant_total_du,
        statut=Loan.Statut.ACTIF,
    )
    generate_installments_flat_interest(loan)

    loan_request.statut = LoanRequest.Statut.APPROUVEE
    loan_request.decide_par = decided_by
    loan_request.date_decision = timezone.now()
    if date_comite:
        loan_request.date_comite = timezone.now()
    if pv_comite is not None:
        loan_request.pv_comite = pv_comite
    loan_request.save(
        update_fields=["statut", "decide_par", "date_decision", "date_comite", "pv_comite", "updated_at"],
    )

    record_audit(
        action="loan.approved",
        entite_type="Loan",
        entite_id=loan.id,
        user=decided_by,
        details={
            "numero_dossier": loan.numero_dossier,
            "montant": str(loan.montant),
            "taux": str(loan.taux_interet),
            "duree_mois": duree,
            "modalite": modalite,
            "request_id": loan_request.id,
        },
    )

    from django.conf import settings as dj_settings

    from apps_coop.notifications.events import emit_event

    member = loan_request.member
    emit_event(
        "loan.approved",
        member=member,
        context={
            "prenom": member.prenom,
            "numero_dossier": loan.numero_dossier,
            "montant": f"{int(loan.montant):,}".replace(",", " "),
            "duree_mois": loan.duree_mois,
            "taux_pct": f"{float(loan.taux_interet) * 100:.2f}",
            "date_premiere": loan.date_premiere_echeance.isoformat(),
            "portal_url": getattr(dj_settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )
    return loan


def disburse_loan_via_tara(
    loan: Loan,
    *,
    agent,
    recipient_phone: str,
    network: str,
) -> "Payment":
    """Initie un décaissement Mobile Money via Tara (payout).

    Crée un ``Payment(type=decaissement, source=mobile_money, statut=en_attente)``
    puis appelle ``provider.init_payout()``. Le webhook Tara confirmera et
    déclenchera ``_hook_decaissement`` qui passe le Loan en ``actif`` +
    ``date_decaissement=today``.

    Idempotence : si un Payment décaissement existe déjà pour ce Loan
    (``en_attente`` OU ``valide``), on le retourne sans nouvel appel Tara.

    **Note transaction** : volontairement **pas** ``@transaction.atomic`` au
    niveau de la fonction — sinon une ``ProviderError`` rollback la création
    du Payment et on perdrait la trace de l'échec. Le wrapper atomique est
    posé uniquement autour de la phase « idempotence check + create » pour
    sérialiser les appels concurrents.
    """
    import uuid

    from apps_coop.audit.services import record as record_audit
    from apps_coop.payments.models import Payment
    from apps_coop.payments.providers import get_provider
    from apps_coop.payments.providers.base import ProviderError

    # 1) Idempotence + création du Payment (atomique, court).
    with transaction.atomic():
        existing = (
            Payment.objects.filter(
                loan=loan,
                type=Payment.Type.DECAISSEMENT,
                statut__in=[Payment.Statut.EN_ATTENTE, Payment.Statut.VALIDE],
            )
            .order_by("id")
            .first()
        )
        if existing:
            return existing

        payment = Payment.objects.create(
            member=loan.member,
            montant=loan.montant,
            type=Payment.Type.DECAISSEMENT,
            source=Payment.Source.MOBILE_MONEY,
            statut=Payment.Statut.EN_ATTENTE,
            provider_code="tara",
            validated_by=agent,
            date_versement=timezone.now(),
            loan=loan,
            idempotency_key=uuid.uuid4(),
        )

    # 2) Appel provider hors transaction — on veut pouvoir persister un statut
    #    `rejete` en cas d'échec, indépendamment de la transaction d'init.
    provider = get_provider("tara")
    try:
        result = provider.init_payout(
            payment, recipient_phone=recipient_phone, network=network
        )
    except ProviderError as exc:
        payment.statut = Payment.Statut.REJETE
        payment.motif_rejet = str(exc)[:500]
        payment.save(update_fields=["statut", "motif_rejet", "updated_at"])
        record_audit(
            action="loan.disburse_payout_failed",
            entite_type="Loan",
            entite_id=loan.id,
            user=agent,
            details={"reason": str(exc), "retryable": exc.retryable, "payment_id": payment.id},
        )
        raise

    payment.reference_externe = result.provider_reference or ""
    payment.gateway_initiated_at = timezone.now()
    payment.save(update_fields=["reference_externe", "gateway_initiated_at", "updated_at"])

    record_audit(
        action="loan.disburse_payout_initiated",
        entite_type="Loan",
        entite_id=loan.id,
        user=agent,
        details={
            "mode": "tara",
            "payment_id": payment.id,
            "reference_externe": payment.reference_externe,
            "recipient_phone_masked": recipient_phone[:4] + "***" + recipient_phone[-2:],
            "network": network,
        },
    )

    # Mode recette flows complets — auto-validate (cf. settings.PAYMENTS_TEST_AUTO_VALIDATE).
    # Joue le webhook DECAISSEMENT "valide" immédiatement. Le hook
    # `_hook_decaissement` basculera le Loan en `actif` et fixera
    # `date_decaissement = today`.
    from django.conf import settings as dj_settings

    if getattr(dj_settings, "PAYMENTS_TEST_AUTO_VALIDATE", False):
        from apps_coop.payments.services import handle_webhook_event

        handle_webhook_event(
            payment.idempotency_key,
            "valide",
            provider_reference=payment.reference_externe,
            raw_payload={
                "auto_validate": True,
                "mode": "test",
                "kind": "loan_disburse",
            },
        )
        payment.refresh_from_db()

    return payment


@transaction.atomic
def disburse_loan_manual(loan: Loan, *, agent, reference_externe: str, note: str = "") -> "Payment":
    """Enregistre un décaissement manuel (virement bancaire / espèces).

    Cas MVP : on n'utilise pas Tara payout (faute d'autorisation). L'agent
    atteste qu'il a viré l'argent au membre par un autre canal, joint la
    référence externe, et un `Payment(type=decaissement, source=manuel,
    statut=valide)` est créé pour traçabilité. Idempotent : si un décaissement
    valide existe déjà, on retourne celui-là.
    """
    import uuid

    from apps_coop.audit.services import record as record_audit
    from apps_coop.payments.models import Payment

    existing = (
        Payment.objects.filter(
            loan=loan,
            type=Payment.Type.DECAISSEMENT,
            statut=Payment.Statut.VALIDE,
        )
        .order_by("id")
        .first()
    )
    if existing:
        return existing

    payment = Payment.objects.create(
        member=loan.member,
        montant=loan.montant,
        type=Payment.Type.DECAISSEMENT,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        provider_code="",
        reference_externe=reference_externe.strip(),
        validated_by=agent,
        date_versement=timezone.now(),
        date_validation=timezone.now(),
        loan=loan,
        idempotency_key=uuid.uuid4(),
        motif_rejet="",  # not relevant for valid
    )
    record_audit(
        action="loan.disbursed",
        entite_type="Loan",
        entite_id=loan.id,
        user=agent,
        details={
            "mode": "manuel",
            "reference_externe": payment.reference_externe,
            "note": note[:200],
            "montant": str(loan.montant),
        },
    )
    return payment


@transaction.atomic
def reject_loan_request(loan_request: LoanRequest, *, decided_by, motif: str) -> LoanRequest:
    """Reject a request that is in ``en_instruction``. Idempotent on rejected."""
    if loan_request.statut == LoanRequest.Statut.REJETEE:
        return loan_request
    if loan_request.statut != LoanRequest.Statut.EN_INSTRUCTION:
        raise ValueError(
            f"Cannot reject a request with status {loan_request.statut!r}."
        )
    motif = (motif or "").strip()
    if not motif:
        raise ValueError("Un motif de rejet est requis.")

    loan_request.statut = LoanRequest.Statut.REJETEE
    loan_request.motif_rejet = motif
    loan_request.decide_par = decided_by
    loan_request.date_decision = timezone.now()
    loan_request.save(
        update_fields=["statut", "motif_rejet", "decide_par", "date_decision", "updated_at"],
    )
    record_audit(
        action="loan_request.rejected",
        entite_type="LoanRequest",
        entite_id=loan_request.id,
        user=decided_by,
        details={"motif": motif},
    )

    # Email « demande non retenue » (best-effort — ne bloque pas le rejet).
    from django.conf import settings as dj_settings

    from apps_coop.notifications.events import emit_event

    member = loan_request.member
    if getattr(member.user, "email", None):
        try:
            emit_event(
                "loan_request.rejected",
                member=member,
                context={
                    "prenom": member.prenom,
                    "motif": motif,
                    "portal_url": getattr(
                        dj_settings, "FRONTEND_BASE_URL", "http://localhost:3200"
                    ),
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning("loan_request.rejected email skipped", exc_info=True)
    return loan_request


# ---------------------------------------------------------------------------
# Loan renewal — member requests an extension before maturity
# ---------------------------------------------------------------------------


from .terms import RENEWAL_EXTRA_MONTHS


@transaction.atomic
def request_loan_renewal(
    loan: Loan,
    *,
    interets_au_comptant: bool = False,
    nouvelle_duree_mois: int | None = None,
) -> LoanRenewal:
    """Crée une `LoanRenewal(statut=demandee)` pour un crédit en cours.

    Règlement Intérieur, Article 10 : la reconduction accorde **un mois
    supplémentaire fixe et unique**. La demande porte donc toujours sur
    ``RENEWAL_EXTRA_MONTHS`` (= 1 mois) ; le paramètre ``nouvelle_duree_mois``
    est conservé pour compat de signature mais **ignoré** (toute valeur ≠ 1 est
    écrasée). La reconduction n'engendre **aucun frais** : seul le taux est
    majoré (Article 11).

    Article 11 : le taux varie selon le choix du membre :
      - intérêts versés cash à la reconduction → 10 %  → ``interets_au_comptant=True``
      - intérêts reportés avec le capital     → 15 %  → ``interets_au_comptant=False``

    Idempotence : si une `LoanRenewal(statut=demandee)` existe déjà pour
    ce Loan, on la retourne (clic double, etc.).
    """
    if loan.statut not in (Loan.Statut.ACTIF, Loan.Statut.EN_RETARD):
        raise ValueError(
            f"Reconduction impossible : crédit en statut {loan.statut!r}."
        )

    # Une seule reconduction par crédit : un crédit déjà issu d'une reconduction
    # ne peut pas être reconduit à nouveau (bloqué dès la soumission).
    if loan.issu_reconduction:
        raise ValueError(
            "Ce crédit est déjà issu d'une reconduction : "
            "la reconduction n'a lieu qu'une seule fois par crédit."
        )

    # Durée par défaut : +1 mois (Article 10) ; modifiable via AppSetting
    # ``loans.renewal.extra_months`` (EXT-1). On ignore toute valeur reçue
    # côté API : la durée reste pilotée centralement.
    from apps_coop.audit.services import get_int_setting

    duree = get_int_setting("loans.renewal.extra_months", RENEWAL_EXTRA_MONTHS)

    existing = (
        LoanRenewal.objects.select_for_update()
        .filter(loan=loan, statut=LoanRenewal.Statut.DEMANDEE)
        .order_by("-date_demande")
        .first()
    )
    if existing:
        return existing

    renewal = LoanRenewal.objects.create(
        loan=loan,
        nouvelle_duree_mois=duree,
        interets_au_comptant=interets_au_comptant,
    )
    record_audit(
        action="loan_renewal.requested",
        entite_type="LoanRenewal",
        entite_id=renewal.id,
        user=loan.member.user,
        details={
            "loan_id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "nouvelle_duree_mois": duree,
            "interets_au_comptant": interets_au_comptant,
            "solde_restant": str(loan.solde_restant),
        },
    )
    return renewal


@transaction.atomic
def approve_loan_renewal(
    renewal: LoanRenewal,
    *,
    decided_by,
    taux_annuel: Decimal | None = None,
    date_premiere_echeance: date,
) -> Loan:
    """Approuve une demande de reconduction et crée le **nouveau** Loan.

    Règlement, Article 11 : le taux est déterminé par le choix du membre :
      - ``renewal.interets_au_comptant == True``  → 10 %
      - ``renewal.interets_au_comptant == False`` → 15 %
    Si ``taux_annuel`` est explicitement passé (par un staff Django admin),
    sa valeur écrase la valeur réglementaire — utile pour une dérogation.

    Étapes :
      1. Vérifie que ``renewal.statut == demandee`` (aucun frais à régler).
      2. Clôture l'ancien Loan (``statut=cloture``).
      3. Crée une `LoanRequest` synthétique pour respecter la FK OneToOne.
      4. Crée le nouveau Loan en réutilisant le ``solde_restant`` de l'ancien.
      5. Génère l'échéancier via `generate_installments_flat_interest`.
      6. Marque la renewal ``approuvee`` + audit + email.

    Idempotent : si la renewal est déjà ``approuvee``, retourne le Loan
    courant du membre (autre que l'ancien).
    """
    from django.conf import settings as dj_settings

    if renewal.statut == LoanRenewal.Statut.APPROUVEE:
        # Replay possible — on cherche le Loan crédité après la reconduction
        # (le seul `actif` du membre qui ne soit pas l'ancien).
        latest = (
            Loan.objects.filter(member=renewal.loan.member, statut=Loan.Statut.ACTIF)
            .exclude(pk=renewal.loan_id)
            .order_by("-date_decaissement")
            .first()
        )
        if latest:
            return latest
        raise ValueError("Reconduction déjà approuvée mais aucun Loan actif trouvé.")

    if renewal.statut != LoanRenewal.Statut.DEMANDEE:
        raise ValueError(
            f"Impossible d'approuver une reconduction en statut {renewal.statut!r}."
        )

    # La reconduction n'engendre AUCUN frais (Règlement Intérieur) : seul le
    # taux d'intérêt est majoré. Aucun paiement préalable n'est requis avant
    # la décision du comité.

    # Taux applicable : Article 11 — au comptant (≈10 %) si intérêts cash,
    # reporté (≈15 %) sinon. Valeurs modifiables côté admin (RateParam, BR2).
    if taux_annuel is None:
        taux_annuel = get_rate(
            RateParam.Code.RENEWAL_CASH
            if renewal.interets_au_comptant
            else RateParam.Code.RENEWAL_DEFERRED
        )
    if not (Decimal("0") <= Decimal(taux_annuel) <= Decimal("1")):
        raise ValueError("Taux attendu entre 0 et 1 (ex. 0.10 pour 10 %).")

    old_loan = renewal.loan
    member = old_loan.member

    # Base de reconduction (Article 11) : le taux porte sur le **capital
    # restant**, jamais sur des intérêts déjà comptés (« intérêts rattachés
    # une fois »). Le nouveau dû reprend le capital + les intérêts restants,
    # puis ajoute taux × capital_restant :
    #   au comptant (10 %) : capital + intérêts + 10 % × capital
    #   reporté    (15 %) : capital + intérêts + 15 % × capital
    capital_restant, interets_restants = _remaining_capital_and_interest(old_loan)
    if capital_restant <= 0:
        raise ValueError(
            f"Capital restant du crédit {old_loan.numero_dossier} est nul — "
            "rien à reconduire."
        )
    base = _q(capital_restant + interets_restants)
    interets_reconduction = _q(Decimal(taux_annuel) * capital_restant)
    montant_total_du = _q(base + interets_reconduction)

    # 2) Clôture de l'ancien Loan
    old_loan.statut = Loan.Statut.CLOTURE
    old_loan.save(update_fields=["statut", "updated_at"])

    # 3) LoanRequest synthétique pour la FK OneToOne du nouveau Loan.
    synth_request = LoanRequest.objects.create(
        member=member,
        montant_demande=base,
        duree_mois=renewal.nouvelle_duree_mois,
        modalite_paiement=old_loan.modalite_paiement,
        motif=(
            f"Reconduction du crédit {old_loan.numero_dossier} — "
            f"capital restant {capital_restant} + intérêts {interets_restants} XAF."
        ),
        statut=LoanRequest.Statut.APPROUVEE,
        date_decision=timezone.now(),
        decide_par=decided_by,
    )

    # 4) Nouveau Loan — la modalité est conservée (le membre garde sa cadence).
    #    ``montant`` = base reportée (capital+intérêts restants) ; les intérêts
    #    de reconduction sont calculés sur le capital seul (cf. interets_reconduction).
    #    ``issu_reconduction`` empêche une 2ᵉ reconduction de ce crédit.
    # EXT-versioning : reconduction = nouveau contrat → on re-fige le taux
    # de pénalité courant (peut différer de l'ancien crédit).
    taux_penalite_fige = get_rate(RateParam.Code.LATE_PENALTY)

    nouveau_loan = Loan.objects.create(
        loan_request=synth_request,
        member=member,
        numero_dossier=_next_numero_dossier(),
        montant=base,
        taux_interet=taux_annuel,
        taux_penalite=taux_penalite_fige,
        duree_mois=renewal.nouvelle_duree_mois,
        modalite_paiement=old_loan.modalite_paiement,
        date_decaissement=date.today(),
        date_premiere_echeance=date_premiere_echeance,
        montant_total_du=montant_total_du,
        solde_restant=montant_total_du,
        statut=Loan.Statut.ACTIF,
        issu_reconduction=True,
    )

    # 5) Échéancier — intérêts de reconduction calculés sur le capital restant.
    generate_installments_flat_interest(
        nouveau_loan, interets_totaux=interets_reconduction
    )

    # 6) Renewal close
    renewal.statut = LoanRenewal.Statut.APPROUVEE
    renewal.date_decision = timezone.now()
    renewal.save(update_fields=["statut", "date_decision", "updated_at"])

    record_audit(
        action="loan_renewal.approved",
        entite_type="LoanRenewal",
        entite_id=renewal.id,
        user=decided_by,
        details={
            "ancien_dossier": old_loan.numero_dossier,
            "nouveau_dossier": nouveau_loan.numero_dossier,
            "capital_restant": str(capital_restant),
            "interets_restants": str(interets_restants),
            "interets_reconduction": str(interets_reconduction),
            "duree_mois": renewal.nouvelle_duree_mois,
            "taux_annuel": str(taux_annuel),
            "montant_total_du": str(nouveau_loan.montant_total_du),
        },
    )

    from apps_coop.notifications.events import emit_event

    emit_event(
        "loan_renewal.approved",
        member=member,
        context={
            "prenom": member.prenom,
            "ancien_dossier": old_loan.numero_dossier,
            "nouveau_dossier": nouveau_loan.numero_dossier,
            "montant_total_du": f"{int(nouveau_loan.montant_total_du):,}".replace(",", " "),
            "duree_mois": renewal.nouvelle_duree_mois,
            "taux_pct": f"{float(taux_annuel) * 100:.2f}",
            "date_premiere": date_premiere_echeance.isoformat(),
            "portal_url": getattr(dj_settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )
    return nouveau_loan


@transaction.atomic
def reject_loan_renewal(renewal: LoanRenewal, *, decided_by, motif: str) -> LoanRenewal:
    """Rejette une demande de reconduction. Idempotent sur déjà-rejetée."""
    if renewal.statut == LoanRenewal.Statut.REJETEE:
        return renewal
    if renewal.statut != LoanRenewal.Statut.DEMANDEE:
        raise ValueError(
            f"Impossible de rejeter une reconduction en statut {renewal.statut!r}."
        )
    motif = (motif or "").strip()
    if not motif:
        raise ValueError("Un motif de rejet est requis.")

    renewal.statut = LoanRenewal.Statut.REJETEE
    renewal.date_decision = timezone.now()
    renewal.save(update_fields=["statut", "date_decision", "updated_at"])

    record_audit(
        action="loan_renewal.rejected",
        entite_type="LoanRenewal",
        entite_id=renewal.id,
        user=decided_by,
        details={"motif": motif, "loan_id": renewal.loan_id},
    )
    from apps_coop.notifications.events import emit_event
    from django.conf import settings as dj_settings

    emit_event(
        "loan_renewal.rejected",
        member=renewal.loan.member,
        context={
            "prenom": renewal.loan.member.prenom,
            "numero_dossier": renewal.loan.numero_dossier,
            "motif": motif,
            "portal_url": getattr(dj_settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )
    return renewal


# ---------------------------------------------------------------------------
# Cycle contentieux (nouveau) — pénalité globale + saisie épargne automatique
# ---------------------------------------------------------------------------


def _quantize(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic
def apply_global_penalty(loan: Loan, *, taux: Decimal | None = None) -> Decimal:
    """Applique la pénalité globale ``taux × solde_restant`` au crédit.

    Idempotent : si la pénalité a déjà été appliquée (champ
    ``penalite_globale_appliquee_at`` non NULL), retourne ``Decimal("0")``.
    Sinon :
      - calcule ``penalite = taux × solde_restant``
      - l'ajoute au ``solde_restant``
      - marque l'application avec la date courante
      - retourne le montant de pénalité appliqué

    ``taux`` par défaut = ``RateParam.LATE_PENALTY`` (50 %, modifiable via
    l'admin). Le crédit doit avoir un ``solde_restant > 0`` (sinon
    ``Decimal("0")``).
    """
    # Re-fetch sous verrou (race contre un remboursement concurrent qui
    # solderait le crédit).
    locked = Loan.objects.select_for_update().get(pk=loan.pk)
    if locked.penalite_globale_appliquee_at is not None:
        return Decimal("0")
    if Decimal(locked.solde_restant) <= 0:
        # Déjà soldé entre-temps — aucune pénalité.
        return Decimal("0")

    if taux is None:
        taux = get_rate(RateParam.Code.LATE_PENALTY)

    penalite = _quantize(Decimal(locked.solde_restant) * Decimal(taux))
    nouveau_solde = Decimal(locked.solde_restant) + penalite
    now = timezone.now()

    locked.solde_restant = nouveau_solde
    locked.penalite_globale_appliquee_at = now
    locked.penalite_globale_montant = penalite
    if locked.statut == Loan.Statut.ACTIF:
        locked.statut = Loan.Statut.EN_RETARD
    locked.save(
        update_fields=[
            "solde_restant",
            "penalite_globale_appliquee_at",
            "penalite_globale_montant",
            "statut",
            "updated_at",
        ]
    )

    record_audit(
        action="loan.penalite_globale_appliquee",
        entite_type="Loan",
        entite_id=locked.id,
        details={
            "taux": str(taux),
            "penalite": str(penalite),
            "nouveau_solde": str(nouveau_solde),
        },
    )
    return penalite


def seize_member_savings_for_loan(loan: Loan) -> dict:
    """R1 — Prélève l'épargne du membre pour solder un crédit en contentieux.

    Refonte 2026 (LOT 13) : façade vers ``seizure_services.seize_for_loan``,
    qui balaie plusieurs sources dans un ordre admin-configurable (épargne
    classique + collecte, débiteur puis avaliste), exclut les
    ``LenderTranche.ENGAGEE`` (Q5), et inclut l'épargne avaliste si
    ``LoanRequest.avaliste`` est posé (§9.2 / Q9.4).

    Tunables : ``loans.seizure.source_order``,
    ``loans.seizure.include_avaliste``, ``loans.seizure.exclude_engaged_tranches``.

    Idempotent. Renvoie le summary dict legacy compatible :
    ``{saisie, epargne_apres, solde_restant_apres, poursuite, no_op}`` +
    nouveaux champs ``saisie_borrower``, ``saisie_avaliste``, ``legs[]``.
    """
    from .seizure_services import seize_for_loan

    result = seize_for_loan(loan)
    return result.to_summary()
