"""Pose ``is_locked: True`` sur les champs câblés en dur des 3 schémas v1
seedés avant CH-4 phase 1.5. Idempotent : si le flag est déjà là, on ne
touche pas. Si la v1 a été modifiée pour retirer un champ, on n'invente rien.
"""
from __future__ import annotations

from django.db import migrations


# Liste des field ids câblés en dur pour chaque kind (mappent vers une colonne
# Django existante des modèles cibles).
LOCKED_FIELDS_BY_KIND = {
    "adhesion": {
        "name", "email", "phone", "whatsapp",
        "city", "quartier_localite", "statut_pro",
        "urgence_nom", "urgence_lien", "urgence_phone",
        "message",
    },
    "loan_request": {
        "montant_demande", "duree_mois", "motif", "modalite_paiement",
    },
    "loan_renewal": {
        "interets_au_comptant",
    },
}

# Renommage éventuel d'un id de champ depuis l'ancien seed vers le nouveau.
# (Avant CH-4 phase 1.5, on avait "montant" et "type_reconduction" ; ils
# mappaient implicitement vers les colonnes "montant_demande" et
# "interets_au_comptant".)
RENAMES_BY_KIND = {
    "loan_request": {"montant": "montant_demande"},
    "loan_renewal": {"type_reconduction": "interets_au_comptant"},
}


def patch_v1_schemas(apps, schema_editor):
    FormSchema = apps.get_model("coop_forms", "FormSchema")
    for kind, locked_ids in LOCKED_FIELDS_BY_KIND.items():
        renames = RENAMES_BY_KIND.get(kind, {})
        for fs in FormSchema.objects.filter(kind=kind):
            schema = fs.schema or {}
            sections = schema.get("sections") or []
            changed = False
            for section in sections:
                for field in section.get("fields") or []:
                    fid = field.get("id")
                    # Renommage transparent ancien → nouveau (avant flag).
                    if fid in renames:
                        field["id"] = renames[fid]
                        fid = field["id"]
                        changed = True
                    if fid in locked_ids and not field.get("is_locked"):
                        field["is_locked"] = True
                        changed = True
            if changed:
                fs.schema = schema
                fs.save(update_fields=["schema", "updated_at"])


def unpatch(apps, schema_editor):
    """Reverse — retire le flag sur les schémas (non destructif)."""
    FormSchema = apps.get_model("coop_forms", "FormSchema")
    for fs in FormSchema.objects.all():
        schema = fs.schema or {}
        sections = schema.get("sections") or []
        changed = False
        for section in sections:
            for field in section.get("fields") or []:
                if field.pop("is_locked", None) is not None:
                    changed = True
        if changed:
            fs.schema = schema
            fs.save(update_fields=["schema", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("coop_forms", "0001_ch4_form_schema"),
    ]

    operations = [
        migrations.RunPython(patch_v1_schemas, unpatch),
    ]
