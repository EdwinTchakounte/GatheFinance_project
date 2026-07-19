"""Rattrapage — justificatifs BRC déposés en pièce jointe de demandes de crédit.

Avant ce lot, une preuve BRC envoyée depuis le formulaire de demande de crédit
(champs ``cga_brc_preuve`` / ``cfp_brc_preuve``) ne créait qu'un ``Document``
rattaché au ``LoanRequest`` : la file de validation ``/brc`` du back-office
restait donc vide et ``Member.is_brc_member`` ne pouvait jamais être posé.

On reconstruit ici les ``BRCDocument`` manquants à partir des pièces déjà
uploadées, en réutilisant le même fichier (pas de copie : on recopie le chemin
de stockage). Idempotent : on ignore ce qui existe déjà.
"""

from django.db import migrations

BRC_FIELD_IDS = ("cga_brc_preuve", "cfp_brc_preuve")


def backfill(apps, schema_editor):
    Document = apps.get_model("members", "Document")
    BRCDocument = apps.get_model("members", "BRCDocument")

    pieces = Document.objects.filter(
        entite_liee_type="LoanRequest",
        schema_field_id__in=BRC_FIELD_IDS,
    ).select_related("member")

    for piece in pieces:
        exists = BRCDocument.objects.filter(
            member_id=piece.member_id,
            loan_request_id=piece.entite_liee_id,
            champ_source=piece.schema_field_id,
        ).exists()
        if exists:
            continue
        BRCDocument.objects.create(
            member_id=piece.member_id,
            fichier=piece.fichier.name,
            nom_original=piece.nom_original,
            taille=piece.taille,
            statut="en_attente",
            loan_request_id=piece.entite_liee_id,
            champ_source=piece.schema_field_id,
        )


def unbackfill(apps, schema_editor):
    """Retire uniquement les lignes reconstruites (jamais un dépôt direct)."""
    BRCDocument = apps.get_model("members", "BRCDocument")
    BRCDocument.objects.filter(
        champ_source__in=BRC_FIELD_IDS,
        statut="en_attente",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("members", "0017_brcdocument_champ_source_brcdocument_loan_request_id"),
    ]

    operations = [migrations.RunPython(backfill, unbackfill)]
