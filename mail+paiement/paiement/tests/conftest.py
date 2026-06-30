"""Configuration Django minimale pour exécuter les tests AUTONOMES du module
paiement (la brique Tara pure), sans avoir besoin du projet complet ni de DB.

Lancer depuis `mail+paiement/paiement/` :

    pytest tests/

Ces tests couvrent la logique qui protège contre les problèmes de
« compensation » / double-comptage : normalisation téléphone, mapping de
statut, parsing + sécurité du webhook, mode mock. Ils ne touchent NI la base
NI les modèles métier — c'est volontaire : on valide la brique réutilisable.
"""
import os
import sys

import django
from django.conf import settings

# Rend le package `payments` importable quand on lance pytest depuis ce dossier.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if not settings.configured:
    settings.configure(
        DEBUG=True,
        TARA_API_KEY="",
        TARA_BUSINESS_ID="",
        TARA_WEBHOOK_SECRET="",
        PUBLIC_BASE_URL="https://api.test",
        DEFAULT_FROM_EMAIL="Test <noreply@test>",
        USE_TZ=True,
    )
    django.setup()
