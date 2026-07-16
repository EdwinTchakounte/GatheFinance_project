"""Découplage prestataire — DEFAULT_PAYMENT_PROVIDER.

Les NOUVEAUX paiements sortants (init payin, décaissement crédit, retrait
épargne) ne codent plus "tara" en dur : ils lisent le réglage
``DEFAULT_PAYMENT_PROVIDER`` via ``default_provider_code()``. Changer de
prestataire = changer ce réglage, sans toucher au code métier.

Contrainte ops : un système de paiement ne doit pas tomber entier sur une faute
de frappe dans l'env → repli sur le provider de secours si le code est inconnu.
"""
from __future__ import annotations

import pytest

from apps_coop.payments import providers as prov_mod
from apps_coop.payments.providers import default_provider_code


def test_lit_le_reglage(settings):
    settings.DEFAULT_PAYMENT_PROVIDER = "tara"
    assert default_provider_code() == "tara"


def test_reglage_vide_retombe_sur_le_secours(settings):
    settings.DEFAULT_PAYMENT_PROVIDER = ""
    assert default_provider_code() == "tara"


def test_code_inconnu_ne_bloque_pas_et_retombe_sur_le_secours(settings, caplog):
    """Typo dans l'env → on journalise et on sert le provider de secours,
    on ne fait PAS tomber tous les paiements."""
    settings.DEFAULT_PAYMENT_PROVIDER = "prestataire-qui-nexiste-pas"
    import logging

    with caplog.at_level(logging.WARNING):
        code = default_provider_code()

    assert code == "tara"
    assert any("n'est pas un prestataire enregistré" in r.message for r in caplog.records)


def test_pointe_vers_un_provider_enregistre(settings, monkeypatch):
    """Un provider fraîchement enregistré devient sélectionnable via le réglage,
    sans toucher aux sites de création de Payment."""
    # default_provider_code() ne fait que vérifier l'appartenance au registre
    # (il n'instancie pas) : on peut mapper le code sur une classe existante.
    monkeypatch.setitem(prov_mod._PROVIDERS, "nouveau", prov_mod.TaraProvider)
    settings.DEFAULT_PAYMENT_PROVIDER = "nouveau"
    assert default_provider_code() == "nouveau"


@pytest.mark.django_db(transaction=True)
def test_le_retrait_momo_porte_le_provider_par_defaut(
    settings, monkeypatch, active_member, admin_user, tara_payout_on
):
    """Bout en bout : l'approbation d'un retrait MOMO crée un Payment
    décaissement dont le ``provider_code`` vient du réglage — preuve que le site
    de création est découplé (avant, "tara" y était écrit en dur)."""
    from decimal import Decimal

    from apps_coop.payments.models import Payment
    from apps_coop.savings.models import WithdrawalRequest
    from apps_coop.savings.services import decide_withdrawal, request_withdrawal

    # Provider factice enregistré sous un code neutre (mappé sur la classe Tara,
    # en mode mock : pas d'appel réseau) puis désigné par défaut.
    monkeypatch.setitem(prov_mod._PROVIDERS, "nouveau", prov_mod.TaraProvider)
    settings.DEFAULT_PAYMENT_PROVIDER = "nouveau"

    acc = active_member.savings_account
    acc.solde = Decimal("50000")
    acc.save(update_fields=["solde"])

    wr = request_withdrawal(
        acc,
        montant=Decimal("15000"),
        mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
        recipient_phone="690000001",
        network="ORANGE",
    )
    decide_withdrawal(wr, decided_by=admin_user, approve=True)

    payment = Payment.objects.get(
        type=Payment.Type.DECAISSEMENT, member=active_member
    )
    assert payment.provider_code == "nouveau"
