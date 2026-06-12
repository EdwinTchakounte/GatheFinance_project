"""CH-4 — Moteur de formulaires dynamiques.

Un ``FormSchema`` stocke en JSON la structure (sections + champs) d'un
formulaire métier. Le rendu côté portail consomme ce JSON via un renderer
React générique ; l'admin l'édite depuis un éditeur visuel.

Versionnement : un seul schéma actif par ``kind`` à un instant T. Les
anciennes versions sont conservées pour audit (les requêtes soumises avant
une activation gardent leur version d'origine — `schema_version` posé sur
les requêtes cibles).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q


class FormSchema(models.Model):
    """Schéma JSON d'un formulaire dynamique versionné.

    Format attendu du champ ``schema`` (JSON) :
      {
        "sections": [
          {
            "id": "identity",
            "title": "Identité",
            "description": "Informations personnelles",
            "fields": [
              {
                "id": "name",
                "type": "text",
                "label": "Nom complet",
                "required": true,
                "placeholder": "Jean Mballa",
                "max_length": 200,
                "help_text": "Tel que sur votre CNI"
              },
              {
                "id": "statut_pro",
                "type": "select",
                "label": "Statut professionnel",
                "options": [
                  {"value": "salarie", "label": "Salarié"},
                  {"value": "independant", "label": "Indépendant"}
                ]
              },
              {
                "id": "carte_cga",
                "type": "file",
                "label": "Carte CGA",
                "accept": "image/*,application/pdf",
                "max_size_mb": 5,
                "condition": {
                  "field": "statut_pro",
                  "operator": "equals",
                  "value": "independant"
                }
              }
            ]
          }
        ]
      }

    Types de champs supportés (renderer portail) :
      text, email, tel, number, textarea, select, radio, checkbox, file, date

    Conditions (visibilité d'un champ) : ``equals``, ``not_equals``, ``in``.

    Flag ``is_locked`` (par champ) :
      True = ce champ est câblé en dur dans le code (mappe vers une colonne de
      ``MembershipRequest`` / ``LoanRequest`` / ``LoanRenewal``). L'admin
      peut renommer le label ou ajuster help_text/placeholder, mais ne peut ni
      changer l'``id``, ni le ``type``, ni le supprimer. La validation backend
      refuse une nouvelle version qui casserait ce contrat (cf.
      ``_validate_locked_fields_preserved`` dans ``serializers.py``).
    """

    class Kind(models.TextChoices):
        ADHESION = "adhesion", "Adhésion"
        LOAN_REQUEST = "loan_request", "Demande de crédit"
        LOAN_RENEWAL = "loan_renewal", "Reconduction crédit"

    kind = models.CharField(
        max_length=32, choices=Kind.choices, db_index=True,
        help_text="Type de formulaire métier (un schéma actif par kind à la fois).",
    )
    version = models.PositiveIntegerField(
        help_text="Numéro de version. Incrémenté par l'admin à chaque modification.",
    )
    title = models.CharField(
        max_length=200,
        help_text="Titre affiché en tête du formulaire (peut différer de la version par défaut).",
    )
    description = models.TextField(
        blank=True,
        help_text="Description courte affichée sous le titre côté portail.",
    )
    schema = models.JSONField(
        default=dict,
        help_text="Structure JSON du formulaire (sections, champs, conditions).",
    )
    is_active = models.BooleanField(
        default=False, db_index=True,
        help_text="Version servie aux utilisateurs. Un seul actif par kind.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="form_schemas_created",
    )
    activated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Horodatage de la dernière activation. Null si jamais activée.",
    )
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="form_schemas_activated",
    )
    notes_admin = models.TextField(
        blank=True,
        help_text="Notes internes admin (changelog, raison de la modification).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Schéma de formulaire"
        verbose_name_plural = "Schémas de formulaire"
        ordering = ["kind", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "version"], name="formschema_unique_kind_version",
            ),
            # Un seul schéma actif par kind (contrainte partielle).
            models.UniqueConstraint(
                fields=["kind"],
                condition=Q(is_active=True),
                name="formschema_one_active_per_kind",
            ),
        ]
        indexes = [
            models.Index(fields=["kind", "is_active"]),
        ]

    def __str__(self) -> str:
        flag = " (actif)" if self.is_active else ""
        return f"{self.get_kind_display()} v{self.version}{flag}"
