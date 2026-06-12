"""Seed des 3 schémas FormSchema initiaux (CH-4).

Reflète les formulaires hard-codés actuels (adhésion, demande crédit,
reconduction) en version 1 active. Idempotent : si une v1 active existe
déjà pour un kind, le seed est ignoré.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps_coop.forms.models import FormSchema


# NB : ``is_locked: true`` signale les champs câblés en dur dans les modèles
# Django (mappent vers une colonne). L'admin peut ajuster label/help/placeholder
# mais pas supprimer ni changer l'id/type — sinon le serializer de soumission
# casserait. Vérifié par ``_validate_locked_fields_preserved`` (CH-4).

ADHESION_SCHEMA = {
    "sections": [
        {
            "id": "identity",
            "title": "Identité",
            "description": "Informations de base.",
            "fields": [
                {"id": "name", "type": "text", "label": "Nom complet", "required": True, "max_length": 200, "placeholder": "Jean Mballa", "is_locked": True},
                {"id": "email", "type": "email", "label": "Adresse e-mail", "required": True, "placeholder": "vous@exemple.com", "is_locked": True},
                {"id": "phone", "type": "tel", "label": "Téléphone", "required": True, "placeholder": "+237 6XX XX XX XX", "is_locked": True},
                {"id": "whatsapp", "type": "tel", "label": "WhatsApp (optionnel)", "required": False, "placeholder": "+237 6XX XX XX XX", "is_locked": True},
            ],
        },
        {
            "id": "location",
            "title": "Localisation",
            "fields": [
                {"id": "city", "type": "text", "label": "Ville", "required": True, "max_length": 160, "is_locked": True},
                {"id": "quartier_localite", "type": "text", "label": "Quartier / localité", "required": False, "max_length": 200, "is_locked": True},
            ],
        },
        {
            "id": "professional",
            "title": "Statut professionnel",
            "fields": [
                {
                    "id": "statut_pro",
                    "type": "select",
                    "label": "Catégorie",
                    "required": False,
                    "is_locked": True,
                    "options": [
                        {"value": "salarie", "label": "Salarié"},
                        {"value": "independant", "label": "Indépendant / commerçant"},
                        {"value": "etudiant", "label": "Étudiant"},
                        {"value": "autre", "label": "Autre"},
                    ],
                },
            ],
        },
        {
            "id": "emergency",
            "title": "Contact d'urgence",
            "fields": [
                {"id": "urgence_nom", "type": "text", "label": "Nom", "required": False, "max_length": 200, "is_locked": True},
                {"id": "urgence_lien", "type": "text", "label": "Lien (parent, conjoint…)", "required": False, "max_length": 80, "is_locked": True},
                {"id": "urgence_phone", "type": "tel", "label": "Téléphone", "required": False, "max_length": 40, "is_locked": True},
            ],
        },
        {
            "id": "motivation",
            "title": "Motivation",
            "fields": [
                {"id": "message", "type": "textarea", "label": "Pourquoi rejoindre Gathe Finance ?", "required": False, "placeholder": "Quelques mots…", "is_locked": True},
            ],
        },
    ],
}


LOAN_REQUEST_SCHEMA = {
    "sections": [
        {
            "id": "demande",
            "title": "Votre demande",
            "fields": [
                {"id": "montant_demande", "type": "number", "label": "Montant demandé (XAF)", "required": True, "min": 10000, "is_locked": True},
                {"id": "duree_mois", "type": "number", "label": "Durée souhaitée (mois)", "required": True, "min": 1, "max": 24, "is_locked": True},
                {"id": "motif", "type": "textarea", "label": "Motif de la demande", "required": True, "placeholder": "Acquisition de matériel, fonds de roulement…", "is_locked": True},
            ],
        },
        {
            "id": "modalite",
            "title": "Modalité de remboursement",
            "fields": [
                {
                    "id": "modalite_paiement",
                    "type": "select",
                    "label": "Fréquence",
                    "required": True,
                    "is_locked": True,
                    "options": [
                        {"value": "journalier", "label": "Journalier"},
                        {"value": "hebdomadaire", "label": "Hebdomadaire"},
                        {"value": "mensuel", "label": "Mensuel"},
                    ],
                },
            ],
        },
    ],
}


LOAN_RENEWAL_SCHEMA = {
    "sections": [
        {
            "id": "reconduction",
            "title": "Reconduction",
            "description": "La reconduction ajoute 1 mois fixe à votre crédit en cours.",
            "fields": [
                {
                    "id": "interets_au_comptant",
                    "type": "select",
                    "label": "Type",
                    "required": True,
                    "is_locked": True,
                    "options": [
                        {"value": "true", "label": "Comptant (10 % sur capital restant)"},
                        {"value": "false", "label": "Reporté (15 % sur capital restant)"},
                    ],
                },
                {"id": "motif", "type": "textarea", "label": "Motif de la reconduction", "required": False},
            ],
        },
    ],
}


SEED_DATA = [
    (FormSchema.Kind.ADHESION, "Demande d'adhésion", "Formulaire public d'adhésion à la coopérative.", ADHESION_SCHEMA),
    (FormSchema.Kind.LOAN_REQUEST, "Demande de crédit", "Formulaire de demande de crédit (CH-5 enrichira avec questions conditionnelles).", LOAN_REQUEST_SCHEMA),
    (FormSchema.Kind.LOAN_RENEWAL, "Reconduction de crédit", "Formulaire de reconduction d'un crédit en cours.", LOAN_RENEWAL_SCHEMA),
]


class Command(BaseCommand):
    help = "Seed des 3 schémas FormSchema initiaux (v1 active)."

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        with transaction.atomic():
            for kind, title, description, schema in SEED_DATA:
                if FormSchema.objects.filter(kind=kind, is_active=True).exists():
                    skipped += 1
                    self.stdout.write(f"  ↷ {kind} déjà actif — skip.")
                    continue
                FormSchema.objects.create(
                    kind=kind,
                    version=1,
                    title=title,
                    description=description,
                    schema=schema,
                    is_active=True,
                    activated_at=timezone.now(),
                    notes_admin="Seed initial CH-4 — reflète le formulaire hard-codé existant.",
                )
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ {kind} v1 seedé."))
        self.stdout.write(f"\nCréés : {created} · Ignorés (déjà actifs) : {skipped}.")
