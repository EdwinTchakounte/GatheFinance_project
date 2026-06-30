"""Tests AUTONOMES de la brique Tara (sans DB, sans modèles métier).

Objectif : garantir que le cœur réutilisable du module paiement — celui qui
évite les bugs de compensation / double-comptage — est correct avant toute
intégration dans un nouveau projet.

On valide :
  - normalisation des numéros de téléphone (format Tara 2376xxxxxxx) ;
  - table de mapping statut Tara → statut interne ;
  - parsing + sécurité du webhook (matching key, businessId, payloads cassés) ;
  - mode mock (pas d'appel HTTP quand les credentials manquent).
"""
import types

import pytest

from payments.providers.base import ProviderError, WebhookEvent
from payments.providers.tara import TaraProvider, _STATUS_MAP


# --------------------------------------------------------------------------
# Normalisation téléphone — Tara veut 2376xxxxxxx (sans +, sans espace)
# --------------------------------------------------------------------------
class TestNormalizePhone:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("237699123456", "237699123456"),       # déjà au format
            ("0699123456", "237699123456"),          # format national → préfixe 237
            ("699123456", "237699123456"),           # sans indicatif → préfixe 237
            ("+237 6 99 12 34 56", "237699123456"),   # avec +, espaces
            ("(237)-699-123-456", "237699123456"),    # ponctuation parasite
        ],
    )
    def test_normalise_vers_format_tara(self, raw, expected):
        assert TaraProvider._normalize_phone(raw) == expected

    def test_numero_vide_leve_provider_error(self):
        with pytest.raises(ProviderError):
            TaraProvider._normalize_phone("")

    def test_numero_sans_chiffre_leve_provider_error(self):
        with pytest.raises(ProviderError):
            TaraProvider._normalize_phone("abc-def")


# --------------------------------------------------------------------------
# Mapping de statut Tara → statut interne (valide / en_attente / rejete)
# --------------------------------------------------------------------------
class TestStatusMap:
    @pytest.mark.parametrize("raw", ["SUCCESS", "VALIDATED", "COMPLETED", "PAID"])
    def test_statuts_succes(self, raw):
        assert _STATUS_MAP[raw] == "valide"

    @pytest.mark.parametrize("raw", ["PENDING", "INITIATED"])
    def test_statuts_en_attente(self, raw):
        assert _STATUS_MAP[raw] == "en_attente"

    @pytest.mark.parametrize("raw", ["FAILED", "REJECTED", "CANCELLED", "ERROR"])
    def test_statuts_rejetes(self, raw):
        assert _STATUS_MAP[raw] == "rejete"

    def test_statut_inconnu_absent_de_la_table(self):
        # Un statut inconnu n'est PAS dans la table — le code appelant tombe
        # alors sur le défaut prudent "en_attente" (jamais "valide").
        assert "WHATEVER" not in _STATUS_MAP


# --------------------------------------------------------------------------
# Webhook — matching key, sécurité businessId, payloads cassés, statut
# --------------------------------------------------------------------------
class TestVerifyWebhook:
    def _provider(self, business_id=""):
        p = TaraProvider()
        p.business_id = business_id  # surcharge l'instance (settings non requis)
        return p

    def test_match_par_product_id(self):
        """productId (notre idempotency_key UUID) est la clé de matching."""
        p = self._provider()
        ev = p.verify_webhook(
            b'{"productId":"uuid-1","paymentId":"TARA42","status":"SUCCESS"}', ""
        )
        assert isinstance(ev, WebhookEvent)
        assert ev.payment_idempotency_key == "uuid-1"
        assert ev.provider_reference == "TARA42"   # paymentId Tara conservé pour audit
        assert ev.status == "valide"

    def test_fallback_sur_collection_id_si_pas_de_product_id(self):
        """Anciens webhooks Tara sans productId → fallback sur collectionId."""
        p = self._provider()
        ev = p.verify_webhook(
            b'{"collectionId":"COL-7","paymentId":"TARA9","status":"PENDING"}', ""
        )
        assert ev.payment_idempotency_key == "COL-7"
        assert ev.status == "en_attente"

    def test_statut_echec_mappe_rejete(self):
        p = self._provider()
        ev = p.verify_webhook(b'{"productId":"u","status":"FAILED"}', "")
        assert ev.status == "rejete"

    def test_statut_inconnu_tombe_sur_en_attente(self):
        p = self._provider()
        ev = p.verify_webhook(b'{"productId":"u","status":"PIZZA"}', "")
        assert ev.status == "en_attente"

    def test_business_id_correct_passe(self):
        p = self._provider(business_id="BIZ-1")
        ev = p.verify_webhook(
            b'{"productId":"u","businessId":"BIZ-1","status":"SUCCESS"}', ""
        )
        assert ev.status == "valide"

    def test_business_id_mismatch_rejete(self):
        """Défense en profondeur : un webhook ciblant un autre businessId
        est refusé même si l'URL secrète a fuité."""
        p = self._provider(business_id="BIZ-1")
        with pytest.raises(ProviderError):
            p.verify_webhook(
                b'{"productId":"u","businessId":"ATTACKER","status":"SUCCESS"}', ""
            )

    def test_body_json_casse_leve_provider_error(self):
        p = self._provider()
        with pytest.raises(ProviderError):
            p.verify_webhook(b"{not-json", "")

    def test_body_vide_donne_cle_vide(self):
        """Body vide → JSON {} → clé vide (le handler côté service décidera)."""
        p = self._provider()
        ev = p.verify_webhook(b"", "")
        assert ev.payment_idempotency_key == ""
        assert ev.status == "en_attente"


# --------------------------------------------------------------------------
# Mode mock — aucun appel HTTP quand les credentials Tara manquent
# --------------------------------------------------------------------------
class TestMockMode:
    def test_mock_mode_actif_sans_credentials(self):
        p = TaraProvider()
        p.api_key = ""
        p.business_id = ""
        assert p._mock_mode is True

    def test_mock_mode_inactif_avec_credentials(self):
        p = TaraProvider()
        p.api_key = "key"
        p.business_id = "biz"
        assert p._mock_mode is False

    def test_init_payin_mock_ne_fait_pas_de_http(self):
        p = TaraProvider()
        p.api_key = ""
        p.business_id = ""
        fake_payment = types.SimpleNamespace(
            idempotency_key="uuid-mock", montant=1000, type="EPARGNE"
        )
        res = p.init_payin(fake_payment, phone="699123456", network="MTN")
        assert res.provider_reference == "MOCK-uuid-mock"
        assert res.payment_url is None
        assert res.raw.get("mock") is True

    def test_check_status_mock_reste_en_attente(self):
        p = TaraProvider()
        p.api_key = ""
        p.business_id = ""
        fake_payment = types.SimpleNamespace(idempotency_key="uuid-mock")
        assert p.check_status(fake_payment) == "en_attente"
