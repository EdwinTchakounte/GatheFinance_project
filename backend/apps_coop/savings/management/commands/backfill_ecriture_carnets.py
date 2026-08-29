"""Backfill du carnet sur les écritures historiques.

Contexte : chaque écriture d'épargne (collecte / classique) et de collecte
particulière (tontine / caisse) porte désormais son carnet (``booklet_order``).
Les écritures créées AVANT ce câblage ont ``booklet_order = NULL`` : elles
n'apparaissent donc sous aucun carnet dans la vue « par carnet ».

Cette commande rattache chaque écriture orpheline au carnet **actif à sa date**
(``BookletOrder.for_member_at(member, date, type)``), typé selon le produit :
collecte / classique → carnet COLLECTE ; tontine → carnet TONTINE ; caisse →
carnet CAISSE_SCOLAIRE. Une écriture antérieure au premier carnet du membre
reste NULL (aucun carnet n'existait à cette date — normal).

Idempotente et non destructive : ne touche QUE les écritures à ``booklet_order``
NULL, ne modifie jamais montant / solde. Lancer d'abord en simulation :

    python manage.py backfill_ecriture_carnets            # dry-run (par défaut)
    python manage.py backfill_ecriture_carnets --commit    # applique
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps_coop.members.models import BookletOrder


class Command(BaseCommand):
    help = "Rattache les écritures historiques (booklet_order NULL) au carnet actif à leur date."

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Applique réellement (sinon simulation / dry-run).",
        )

    def handle(self, *args, **options):
        from apps_coop.savings.models import (
            ClassicSavingsTransaction,
            SavingsTransaction,
        )
        from apps_coop.special_collections.models import (
            SpecialCollectionTransaction,
        )

        commit = options["commit"]
        T = BookletOrder.Type
        # Cache par (member_id, type, jour) → carnet, pour éviter une requête
        # for_member_at par écriture.
        cache: dict = {}

        def resolve(member, carnet_type, when):
            day = when.date()
            key = (member.id, carnet_type, day)
            if key not in cache:
                cache[key] = BookletOrder.for_member_at(member, day, carnet_type)
            return cache[key]

        stats = {"savings": [0, 0], "classic": [0, 0], "special": [0, 0]}

        with transaction.atomic():
            # 1) Collecte journalière → carnet COLLECTE.
            for tx in (
                SavingsTransaction.objects.filter(booklet_order__isnull=True)
                .select_related("account__member")
            ):
                stats["savings"][0] += 1
                bo = resolve(tx.account.member, T.COLLECTE, tx.date)
                if bo is not None:
                    if commit:
                        SavingsTransaction.objects.filter(pk=tx.pk).update(
                            booklet_order=bo
                        )
                    stats["savings"][1] += 1

            # 2) Épargne classique → carnet COLLECTE (même carnet physique).
            for tx in (
                ClassicSavingsTransaction.objects.filter(booklet_order__isnull=True)
                .select_related("account__member")
            ):
                stats["classic"][0] += 1
                bo = resolve(tx.account.member, T.COLLECTE, tx.date)
                if bo is not None:
                    if commit:
                        ClassicSavingsTransaction.objects.filter(pk=tx.pk).update(
                            booklet_order=bo
                        )
                    stats["classic"][1] += 1

            # 3) Collectes particulières → carnet TONTINE / CAISSE selon le cycle.
            type_by_collection = {
                "tontine_alimentaire": T.TONTINE,
                "caisse_scolaire": T.CAISSE_SCOLAIRE,
            }
            for tx in (
                SpecialCollectionTransaction.objects.filter(booklet_order__isnull=True)
                .select_related("membership__member", "membership__cycle")
            ):
                stats["special"][0] += 1
                cycle_type = tx.membership.cycle.type
                carnet_type = type_by_collection.get(cycle_type)
                if carnet_type is None:
                    continue
                bo = resolve(tx.membership.member, carnet_type, tx.date)
                if bo is not None:
                    if commit:
                        SpecialCollectionTransaction.objects.filter(pk=tx.pk).update(
                            booklet_order=bo
                        )
                    stats["special"][1] += 1

            if not commit:
                # Dry-run : on annule tout (rien n'a été écrit de toute façon).
                transaction.set_rollback(True)

        mode = "APPLIQUÉ" if commit else "SIMULATION (dry-run — rien écrit)"
        self.stdout.write(f"Backfill carnets écritures — {mode}")
        for label, (seen, matched) in stats.items():
            self.stdout.write(
                f"  {label:8}: {seen} orphelines, {matched} rattachables "
                f"({seen - matched} sans carnet à leur date → laissées NULL)"
            )
        if not commit:
            self.stdout.write("Relancer avec --commit pour appliquer.")
