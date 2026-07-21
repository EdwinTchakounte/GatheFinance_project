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

from apps_coop.audit.services import get_str_setting, record as record_audit
from apps_coop.members.models import Member
from apps_coop.payments.models import RateParam
from apps_coop.payments.rates import get_rate

from .models import Loan, LoanInstallment, LoanRenewal, LoanRequest
from .terms import (
    PaymentModality,
    duration_months_for,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Eligibility — read-only check used by the portal
# ---------------------------------------------------------------------------


@dataclass
class Eligibility:
    eligible: bool
    plafond_max: Decimal  # montant max EMPRUNTABLE SANS AVALISTE (= épargne classique dispo)
    motifs: list[str]
    # Useful context for the UI to display the rules to the member.
    solde_epargne: Decimal  # solde épargne classique total
    ratio_garantie: Decimal


# Réforme garantie 2026 : plus de multiplicateur. Sans avaliste, on emprunte
# jusqu'à sa propre épargne classique disponible (ratio 1:1).
ANCIENNETE_MIN_MOIS = 0  # MVP: no anciennity requirement


def compute_eligibility(member: Member) -> Eligibility:
    """Peut-il soumettre une demande, et jusqu'à combien SANS avaliste ?

    Réforme garantie 2026 :
      1. ``Member.statut == actif``
      2. Pas de ``Loan`` actif / en_retard / contentieux
      3. Pas de ``LoanRequest`` déjà en cours
      4. ``plafond_max`` = épargne classique DISPONIBLE (= montant max
         empruntable en auto-couverture, sans avaliste). Au-delà, le membre
         doit désigner un avaliste — ce n'est PAS un blocage d'éligibilité.

    Le seuil « solde ≥ 100 XAF » disparaît : un membre sans épargne classique
    reste éligible (il passera par la voie avaliste ou campagne).
    """
    from .avaliste_services import _member_available_savings, _member_total_savings

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
            LoanRequest.Statut.EN_ATTENTE_AVALISTE,
            LoanRequest.Statut.EN_VALIDATION_CAMPAGNE,
            LoanRequest.Statut.APPROUVEE_PROVISOIRE,
        ],
    ).count()
    if pending_requests:
        motifs.append(
            "Tu as déjà une demande en cours. "
            "Attends la décision avant d'en soumettre une nouvelle."
        )

    # Plafond sans avaliste = épargne classique disponible (déduit le gel déjà pris).
    solde_classique = _member_total_savings(member)
    dispo = _member_available_savings(member)

    return Eligibility(
        eligible=len(motifs) == 0,
        plafond_max=dispo,
        motifs=motifs,
        solde_epargne=solde_classique,
        ratio_garantie=Decimal("1"),
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

    Deux modes selon ``loan.mode_retenue_interets`` :

    - **echeances** (legacy) : intérêts répartis sur les échéances.

        intérêts_totaux = montant × taux            (10 % par défaut)
        n               = durée_mois × cadence(modalité)
        capital_par_éch = montant / n
        intérêts_par_éch = intérêts_totaux / n
        mensualité      = capital_par_éch + intérêts_par_éch

    - **source** (CH-11, par défaut 2026-06-12) : intérêts retenus à la
      mise à disposition. Le membre rembourse uniquement ce qu'il a touché.

        capital_total   = montant_decaisse_net      (= 90 % du nominal)
        intérêts_éch    = 0
        mensualité      = capital_par_éch (capital pur)

    La dernière échéance absorbe le reliquat d'arrondi pour que la somme des
    capitaux soit exactement le capital pris en charge (idem pour les intérêts).

    ``interets_totaux`` (optionnel) : pour une **reconduction**, les intérêts
    ne se calculent pas sur ``montant`` mais sur le **capital restant**
    (Article 11). On passe alors le montant d'intérêts déjà calculé ; sinon
    (crédit initial) on retombe sur ``montant × taux``.

    L'historique conservait l'ancien nom ``generate_installments_amortissement_constant``
    par compat ; il pointe désormais sur cette fonction (alias en bas du module).
    """
    mode_source = (
        getattr(loan, "mode_retenue_interets", "echeances") == Loan.ModeRetenue.SOURCE
    )

    if mode_source:
        # CH-11 — Le membre rembourse uniquement le net décaissé (capital pur),
        # les intérêts ayant été retenus à la source. interets_totaux est forcé
        # à zéro même si un appelant l'a passé (reconduction n'utilise pas le
        # mode source — guard simple).
        montant = Decimal(loan.montant_decaisse_net or loan.montant)
        interets_totaux = Decimal("0")
    else:
        montant = Decimal(loan.montant)
        if interets_totaux is None:
            taux = Decimal(loan.taux_interet)
            interets_totaux = _q(montant * taux)
        else:
            interets_totaux = _q(Decimal(interets_totaux))

    # Règle 2026 « DATE BUTOIR UNIQUE » : l'échéancier n'est plus fractionné en
    # N mensualités. Une **seule échéance** porte la totalité du montant dû et
    # est exigible à la **date butoir** (= date_premiere_echeance + (durée − 1)
    # mois — inchangée par rapport à l'ancienne dernière échéance, pour ne pas
    # décaler la pénalité ni le contentieux). Le membre rembourse **librement**
    # (montant/moment de son choix) d'ici là : chaque versement s'impute en FIFO
    # sur cette unique ligne (cf. ``repay_loan``). Pénalité (Art. 12) et
    # contentieux se déclenchent quand cette échéance bascule en retard.
    capital = _q(montant)
    interets = _q(interets_totaux)
    deadline = _add_months(
        loan.date_premiere_echeance, max(0, loan.duree_mois - 1)
    )
    inst = LoanInstallment.objects.create(
        loan=loan,
        numero_echeance=1,
        date_echeance=deadline,
        montant_capital=capital,
        montant_interets=interets,
        montant_total=_q(capital + interets),
        statut=LoanInstallment.Statut.A_VENIR,
    )
    return [inst]


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
    # CH-6 — La décision définitive peut suivre soit l'instruction directe
    # (EN_INSTRUCTION) soit l'approbation provisoire + visite terrain
    # (APPROUVEE_PROVISOIRE).
    allowed_from = (
        LoanRequest.Statut.EN_INSTRUCTION,
        LoanRequest.Statut.APPROUVEE_PROVISOIRE,
    )
    if loan_request.statut not in allowed_from:
        raise ValueError(
            f"Cannot approve a request with status {loan_request.statut!r} "
            f"(expected one of {[s.value for s in allowed_from]!r})."
        )

    taux = (
        Decimal(taux_annuel)
        if taux_annuel is not None
        else get_rate(RateParam.Code.LOAN_INTEREST)
    )
    montant = Decimal(loan_request.montant_demande)

    # L4 — Voie garantie matérielle : l'évaluation et la validation du bien
    # relèvent du COMITÉ DES PRÊTS (jugement hors système). Le système
    # n'impose donc AUCUNE règle de couverture ici ; il se contente de tracer
    # la valeur éventuellement saisie par l'admin (cf. LoanGuarantee ci-dessous).

    duree = duration_months_for(montant)
    modalite = loan_request.modalite_paiement or PaymentModality.MENSUEL

    # EXT-versioning : on FIGE le taux de pénalité au décaissement (le membre
    # signe un contrat avec ce taux — un changement admin ultérieur ne doit
    # pas s'appliquer rétroactivement).
    taux_penalite_fige = get_rate(RateParam.Code.LATE_PENALTY)

    # CH-11 — Choix du mode de retenue d'intérêts (toggle AppSetting).
    # Lecture défensive : si la valeur n'est pas exactement "true" (case
    # insensitive), on retombe sur le mode legacy "echeances".
    raw_toggle = (get_str_setting("loans.interest_withheld_at_source", "true") or "").strip().lower()
    interest_at_source = raw_toggle in ("true", "1", "yes", "oui")

    if interest_at_source:
        # Mode "source" (Sinora §5.3) : la coop encaisse 10 % à T0, le membre
        # reçoit 90 % et rembourse seulement ces 90 %.
        interets_retenus_source = _q(montant * taux)
        montant_decaisse_net = _q(montant - interets_retenus_source)
        montant_total_du = montant_decaisse_net
        mode_retenue = Loan.ModeRetenue.SOURCE
    else:
        # Mode legacy : intérêts répartis sur les échéances. Le membre reçoit
        # 100 % du nominal et rembourse capital + intérêts.
        interets_retenus_source = Decimal("0")
        montant_decaisse_net = montant
        montant_total_du = _q(montant + (montant * taux))
        mode_retenue = Loan.ModeRetenue.ECHEANCES

    # CH-12 — Fige le taux de partage prêteurs/coop courant pour éviter qu'un
    # changement admin ultérieur ne s'applique rétroactivement. La valeur
    # courante vit dans l'AppSetting ``lender.interest_share_rate``.
    share_rate_raw = (get_str_setting("lender.interest_share_rate", "0.5") or "0.5").strip()
    try:
        share_rate_fige = Decimal(share_rate_raw)
        if share_rate_fige < 0 or share_rate_fige > 1:
            share_rate_fige = max(Decimal("0"), min(Decimal("1"), share_rate_fige))
    except Exception:  # noqa: BLE001 — valeur AppSetting cassée
        share_rate_fige = Decimal("0.5")

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
        # Filet de sécurité : le crédit est ACTIF mais l'argent n'est pas encore
        # versé. Le décaissement réel (disburse) lèvera ce flag ; d'ici là, le
        # cron de retards l'ignore (pas de pénalité/saisie avant décaissement).
        en_attente_decaissement=True,
        mode_retenue_interets=mode_retenue,
        montant_decaisse_net=montant_decaisse_net,
        interets_retenus_source=interets_retenus_source,
        interest_share_rate_fige=share_rate_fige,
    )
    generate_installments_flat_interest(loan)

    # L4 — Matérialise la garantie évaluée en LoanGuarantee (traçabilité).
    if loan_request.garantie_materielle:
        from .models import LoanGuarantee

        LoanGuarantee.objects.create(
            loan=loan,
            type_garantie=LoanGuarantee.TypeGarantie.BIEN_IMMOBILIER,
            description=loan_request.garantie_description or "",
            valeur_estimee=Decimal(loan_request.garantie_valeur_estimee or 0),
        )

    # CH-8 — Pose la date butoire formelle = date de la dernière échéance
    # générée. C'est cette date (et non les échéances individuelles) qui
    # déclenche la pénalité globale et le contentieux. L'admin peut la prolonger
    # via /extend-deadline/ avec motif (extension exceptionnelle).
    last_echeance = (
        loan.installments.order_by("-date_echeance")
        .values_list("date_echeance", flat=True)
        .first()
    )
    if last_echeance is not None:
        loan.date_butoire = last_echeance
        loan.save(update_fields=["date_butoire", "updated_at"])

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
    from apps_coop.payments.providers import default_provider_code, get_provider
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

        # CH-11 — Le montant versé est le NET (montant_decaisse_net) en mode
        # source. Fallback sur loan.montant pour les Loans legacy sans champ.
        montant_versement = Decimal(loan.montant_decaisse_net or loan.montant)
        payment = Payment.objects.create(
            member=loan.member,
            montant=montant_versement,
            type=Payment.Type.DECAISSEMENT,
            source=Payment.Source.MOBILE_MONEY,
            statut=Payment.Statut.EN_ATTENTE,
            provider_code=default_provider_code(),
            validated_by=agent,
            date_versement=timezone.now(),
            loan=loan,
            idempotency_key=uuid.uuid4(),
        )

    # 2) Appel provider hors transaction — on veut pouvoir persister un statut
    #    `rejete` en cas d'échec, indépendamment de la transaction d'init.
    provider = get_provider(payment.provider_code or default_provider_code())
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
            # CH-11 — Traçabilité de la retenue à la source. Le payment.montant
            # est le NET ; on consigne le brut nominal et la retenue séparément.
            "montant_brut_nominal": str(loan.montant),
            "montant_decaisse_net": str(montant_versement),
            "interets_retenus_source": str(loan.interets_retenus_source or "0"),
            "mode_retenue_interets": loan.mode_retenue_interets,
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

    # CH-11 — Idem que disburse_loan_via_tara : on verse le NET (90 %) en
    # mode source. Fallback sur loan.montant pour les Loans legacy.
    montant_versement = Decimal(loan.montant_decaisse_net or loan.montant)
    payment = Payment.objects.create(
        member=loan.member,
        montant=montant_versement,
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
    # Le décaissement MANUEL doit produire les MÊMES effets métier que le payout
    # Tara : Loan actif + date_decaissement + distribution de la part d'intérêts
    # aux prêteurs (mode source, tranches de placement engagées). Sans ça, en
    # payout 100 % manuel, les prêteurs n'étaient jamais crédités.
    from apps_coop.payments.services import _hook_decaissement

    _hook_decaissement(payment, {})

    record_audit(
        action="loan.disbursed",
        entite_type="Loan",
        entite_id=loan.id,
        user=agent,
        details={
            "mode": "manuel",
            "reference_externe": payment.reference_externe,
            "note": note[:200],
            # CH-11 — Traçabilité de la retenue à la source. ``montant`` est
            # le brut nominal, ``montant_decaisse_net`` est le NET versé.
            "montant_brut_nominal": str(loan.montant),
            "montant_decaisse_net": str(montant_versement),
            "interets_retenus_source": str(loan.interets_retenus_source or "0"),
            "mode_retenue_interets": loan.mode_retenue_interets,
        },
    )
    return payment


def tara_payout_enabled() -> bool:
    """La plateforme initie-t-elle des payouts Tara (money OUT) ?

    Défaut **FALSE** : en prod l'admin fait le virement sur Tara lui-même puis
    vient marquer « payé » (décaissement / retrait manuel). Réactivable via
    l'AppSetting ``payments.tara_payout.enabled`` si l'autorisation Tara arrive.
    """
    from apps_coop.audit.services import get_str_setting

    return (get_str_setting("payments.tara_payout.enabled", "false") or "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def carnet_fee_amount() -> Decimal:
    """Montant des frais de carnet (``FeeType.CARNET``). 0 si non configuré."""
    from apps_coop.payments.models import FeeType

    fee = (
        FeeType.objects.filter(code=FeeType.Code.CARNET, actif=True)
        .values_list("montant", flat=True)
        .first()
    )
    return Decimal(fee) if fee is not None else Decimal("0")


def campaign_member_needs_carnet(member) -> bool:
    """True si ``member`` est un bénéficiaire CRÉÉ via campagne
    (``member.microcampaign`` posé) qui n'a encore AUCUN carnet.

    Règle métier 2026 : un membre créé via campagne doit obligatoirement
    posséder un carnet — les versements/écritures de collecte s'imputent au
    carnet (``booklet_order``). Tant qu'il n'en a pas, sa demande de crédit
    reste bloquée à la porte des frais (le carnet est facturé et réglé à la
    demande de crédit, en même temps que les frais d'étude).
    """
    if getattr(member, "microcampaign_id", None) is None:
        return False
    from apps_coop.members.models import BookletOrder

    return not BookletOrder.objects.filter(member=member).exists()


def study_fee_for(campaign=None) -> Decimal:
    """Frais d'étude applicables : override campagne si défini, sinon FeeType.
    DEMANDE_CREDIT. 0 = étude gratuite."""
    if campaign is not None and getattr(campaign, "frais_etude_montant", None) is not None:
        return Decimal(campaign.frais_etude_montant)
    from apps_coop.payments.models import FeeType

    fee = (
        FeeType.objects.filter(code=FeeType.Code.DEMANDE_CREDIT, actif=True)
        .values_list("montant", flat=True)
        .first()
    )
    return Decimal(fee) if fee is not None else Decimal("0")


def status_after_prevoie(loan_request) -> str:
    """Statut d'une demande APRÈS la pré-étape d'une voie (avaliste accepté /
    campagne validée). On passe par la porte « frais d'étude » (EN_ATTENTE) si
    des frais sont dus, sinon directement en instruction. Ainsi TOUTES les voies
    réclament les frais d'étude au même endroit (statut en_attente = à payer).

    Frais déjà réglés → EN_INSTRUCTION direct. Sans ce garde-fou, l'ordre
    « frais d'abord, avaliste ensuite » renvoyait la demande en EN_ATTENTE
    (« frais à percevoir ») alors même que ``frais_demande_credit_paye`` est
    vrai — elle restait bloquée à réclamer des frais déjà encaissés."""
    if getattr(loan_request, "frais_demande_credit_paye", False):
        return LoanRequest.Statut.EN_INSTRUCTION
    return (
        LoanRequest.Statut.EN_ATTENTE
        if study_fee_for(getattr(loan_request, "microcampaign", None)) > 0
        else LoanRequest.Statut.EN_INSTRUCTION
    )


@transaction.atomic
def reject_loan_request(loan_request: LoanRequest, *, decided_by, motif: str) -> LoanRequest:
    """Reject a request that is in ``en_instruction``. Idempotent on rejected."""
    if loan_request.statut == LoanRequest.Statut.REJETEE:
        return loan_request
    # CH-6 — rejet possible aussi depuis APPROUVEE_PROVISOIRE (visite défavorable).
    allowed_from = (
        LoanRequest.Statut.EN_INSTRUCTION,
        LoanRequest.Statut.APPROUVEE_PROVISOIRE,
    )
    if loan_request.statut not in allowed_from:
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

    # A4 . Pas de reconduction tant qu'une penalite Art.12 reste impayee.
    # On considere comme impayee toute penalite > 0 sur une echeance non
    # encore soldee (statut != PAYEE). Si l'echeance est deja payee, c'est
    # que la penalite a ete versee avec le capital + interets de l'echeance.
    from .models import LoanInstallment

    penalite_impayee = (
        LoanInstallment.objects
        .filter(loan=loan, montant_penalite__gt=Decimal("0"))
        .exclude(statut=LoanInstallment.Statut.PAYEE)
        .exists()
    )
    if penalite_impayee:
        raise ValueError(
            "Reconduction impossible : une penalite Article 12 reste a payer "
            "sur ce credit. Solde les echeances en retard avant de reconduire."
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

    # Le montant à verser au comptant est FIGÉ ici. Avant, il n'existait que
    # côté client (recalculé à l'affichage) et transitoirement à l'approbation :
    # le membre lisait « tu verses les intérêts maintenant » sans que rien ne
    # soit jamais réclamable. On le persiste pour pouvoir l'encaisser.
    from apps_coop.payments.rates import get_rate
    from apps_coop.payments.models import RateParam

    # Base = tout ce qu'il reste à remettre (capital + intérêts résiduels).
    # Reconduire 25 000 coûte 15 % de 25 000, EN PLUS des 25 000 à rembourser
    # (nouveau crédit = 28 750).
    capital_restant, interets_restants = _remaining_capital_and_interest(loan)
    montant_a_reconduire = _q(capital_restant + interets_restants)
    # 2026-07 : VOLET UNIQUE 15 %. Plus de choix « comptant 10 % / reporté 15 % » :
    # le coût de reconduction est TOUJOURS 15 % du reste. Le paiement anticipé de
    # ces intérêts reste possible (pay_renewal_interest_from_savings) mais ne
    # change pas le taux — c'est juste régler d'avance ce qui sinon est reporté.
    interets_au_comptant = False
    taux = get_rate(RateParam.Code.RENEWAL_DEFERRED)
    interets_dus = _q(Decimal(taux) * montant_a_reconduire)

    renewal = LoanRenewal.objects.create(
        loan=loan,
        nouvelle_duree_mois=duree,
        interets_au_comptant=interets_au_comptant,
        montant_a_reconduire_snapshot=montant_a_reconduire,
        interets_dus=interets_dus,
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
            "interets_dus": str(interets_dus),
            "montant_a_reconduire": str(montant_a_reconduire),
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

    # Les intérêts de reconduction peuvent être versés AVANT ou APRÈS la
    # décision — l'approbation n'est donc jamais bloquée par le paiement. Ce
    # qui change, c'est seulement le traitement à l'approbation : déjà
    # encaissés → rien à étaler ; pas encore → reportés sur l'échéancier.

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

    # Base de reconduction : le taux porte sur TOUT ce qu'il reste à remettre
    # (capital + intérêts résiduels), jamais sur le montant initial. Le
    # nouveau dû reprend cette base, puis ajoute taux × base :
    #   reconduire 50 000 → 15 % × 50 000 = 7 500 d'intérêts, EN PLUS des
    #   50 000 qui restent à rembourser.
    capital_restant, interets_restants = _remaining_capital_and_interest(old_loan)
    if capital_restant <= 0:
        raise ValueError(
            f"Capital restant du crédit {old_loan.numero_dossier} est nul — "
            "rien à reconduire."
        )
    base = _q(capital_restant + interets_restants)
    interets_reconduction = _q(Decimal(taux_annuel) * base)
    # Les intérêts déjà encaissés ne sont pas réintégrés au nouveau dossier :
    # les remettre ferait payer deux fois la même chose (une fois en cash, une
    # fois étalée sur les échéances). On se fie à l'encaissement RÉELLEMENT
    # constaté, pas à l'intention cochée au moment de la demande.
    interets_deja_encaisses = renewal.interets_payes_at is not None
    montant_total_du = (
        base if interets_deja_encaisses else _q(base + interets_reconduction)
    )

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

    # CH-10/11 — La reconduction reste en mode "echeances" volontairement.
    # Le membre ne reçoit pas de nouvelle somme à la reconduction (il a déjà
    # touché ses fonds au décaissement initial), donc la mécanique de retenue
    # à la source (CH-11) ne s'applique pas. Les intérêts de reconduction
    # (Article 11) sont étalés sur les nouvelles échéances : ``echeances`` =
    # comportement légal correct, ``source`` serait incorrect ici.
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
        mode_retenue_interets=Loan.ModeRetenue.ECHEANCES,
        montant_decaisse_net=base,  # membre ne touche rien, mais champ non-NULL pour cohérence
        interets_retenus_source=Decimal("0"),
    )

    # 5) Échéancier — on n'étale que ce qui n'a pas déjà été encaissé.
    interets_a_etaler = (
        Decimal("0") if interets_deja_encaisses else interets_reconduction
    )
    generate_installments_flat_interest(
        nouveau_loan, interets_totaux=interets_a_etaler
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
