"""Commande one-shot pour réconcilier les Payment EN_ATTENTE stuck.

Usage prod :
    docker exec gathe-finance-backend-1 python manage.py reconcile_payments
    docker exec gathe-finance-backend-1 python manage.py reconcile_payments --member-id 2
    docker exec gathe-finance-backend-1 python manage.py reconcile_payments --force-valide --payment-id 37

Le cron `*/5 * * * *` fait déjà ce travail automatiquement, cette commande sert :
- À déclencher la réconciliation IMMÉDIATEMENT (pas attendre le prochain tick).
- À forcer la validation d'un Payment spécifique quand on sait que MoMo a
  débité mais Tara n'a jamais envoyé le webhook (`--force-valide`).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps_coop.payments.models import Payment
from apps_coop.payments.services import handle_webhook_event
from apps_coop.payments.tasks import reconcile_pending_payments


class Command(BaseCommand):
    help = "Reconcile pending Tara payments now (poll Tara status, apply if changed)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--member-id", type=int, default=None,
            help="Restreint au member id donné (debug).",
        )
        parser.add_argument(
            "--payment-id", type=int, default=None,
            help="Force la réconciliation d'un Payment précis.",
        )
        parser.add_argument(
            "--force-valide", action="store_true",
            help="Avec --payment-id : force le passage à valide (cas où MoMo a "
                 "débité mais Tara n'a jamais envoyé de webhook). À utiliser "
                 "avec discernement.",
        )
        parser.add_argument(
            "--batch-size", type=int, default=200,
            help="Nombre max de Payments à traiter par run.",
        )

    def handle(self, *args, **opts):
        # Cas 1 : force valide sur un Payment précis (rattrapage manuel)
        if opts.get("payment_id") and opts.get("force_valide"):
            try:
                payment = Payment.objects.get(pk=opts["payment_id"])
            except Payment.DoesNotExist:
                self.stderr.write(self.style.ERROR(
                    f"Payment #{opts['payment_id']} introuvable.",
                ))
                return
            if payment.statut != Payment.Statut.EN_ATTENTE:
                self.stderr.write(self.style.WARNING(
                    f"Payment #{payment.id} déjà en statut {payment.statut!r} — "
                    f"rien à faire.",
                ))
                return
            self.stdout.write(
                f"Forçage VALIDE sur Payment #{payment.id} "
                f"({payment.type}, {payment.montant} XAF, member={payment.member_id})…",
            )
            handle_webhook_event(
                payment.idempotency_key,
                "valide",
                provider_reference=payment.reference_externe or "",
                raw_payload={"manual_reconcile": True, "command": "reconcile_payments"},
            )
            payment.refresh_from_db()
            self.stdout.write(self.style.SUCCESS(
                f"Payment #{payment.id} → {payment.statut}",
            ))
            return

        # Cas 2 : réconciliation batch (poll Tara pour les EN_ATTENTE)
        summary = reconcile_pending_payments(batch_size=opts["batch_size"])
        self.stdout.write(self.style.SUCCESS(
            f"reconcile_pending_payments → {summary}",
        ))
