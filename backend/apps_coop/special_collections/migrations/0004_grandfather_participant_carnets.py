"""Reprise (2026-08) : la règle « carnet requis pour verser » ne doit pas
bloquer les participants tontine/caisse DÉJÀ actifs avant son introduction.

Cette migration dote chaque membre ayant une participation VALIDÉE d'un carnet
du type correspondant (tontine / caisse scolaire) s'il n'en a pas déjà un. Le
carnet est créé avec un Payment technique à 0 (source manuelle, validé) — même
procédé que la reprise de carnet antidatée.

Idempotente : réexécutable sans créer de doublon (on saute si un carnet du type
existe déjà pour le membre).
"""
from django.db import migrations


# collection type → (booklet type, carnet payment type)
_MAP = {
    "tontine_alimentaire": ("tontine", "frais_carnet_tontine"),
    "caisse_scolaire": ("caisse_scolaire", "frais_carnet_caisse"),
}


def grandfather(apps, schema_editor):
    from django.utils import timezone

    Membership = apps.get_model("special_collections", "SpecialCollectionMembership")
    BookletOrder = apps.get_model("members", "BookletOrder")
    Payment = apps.get_model("payments", "Payment")

    now = timezone.now()
    seen: set[tuple[int, str]] = set()

    qs = Membership.objects.filter(statut="valide").select_related("member")
    for m in qs.iterator():
        mapping = _MAP.get(m.type)
        if mapping is None:
            continue
        booklet_type, carnet_payment_type = mapping
        key = (m.member_id, booklet_type)
        if key in seen:
            continue
        seen.add(key)

        # Déjà un carnet de ce type ? → rien à faire.
        if BookletOrder.objects.filter(
            member_id=m.member_id, type=booklet_type
        ).exists():
            continue

        payment = Payment.objects.create(
            member_id=m.member_id,
            montant=0,
            type=carnet_payment_type,
            source="manuel",
            statut="valide",
            date_versement=now,
            date_validation=now,
        )
        BookletOrder.objects.create(
            member_id=m.member_id,
            type=booklet_type,
            payment=payment,
            statut="delivree",
            annee=now.year,
            notes_agence="Carnet attribué automatiquement (reprise règle carnet 2026-08).",
        )


def noop(apps, schema_editor):
    # Reprise non réversible (on ne supprime pas des carnets attribués).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("special_collections", "0003_remove_specialcollectioncycle_uniq_open_cycle_per_type_and_more"),
        ("members", "0022_bookletorder_type"),
        ("payments", "0010_payment_special_cycle"),
    ]

    operations = [
        migrations.RunPython(grandfather, noop),
    ]
