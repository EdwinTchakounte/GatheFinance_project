"""Tests de la sauvegarde quotidienne des écritures (`backup_ecritures`).

Vérifie : le fichier JSONL.gz est écrit sous MEDIA_ROOT/coop/backups/, contient
un manifeste + une ligne par écriture, n'altère JAMAIS la base (non destructif),
et purge les backups au-delà de la fenêtre de rétention.
"""
from __future__ import annotations

import gzip
import json
import time
from decimal import Decimal
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from apps_coop.payments.models import Payment
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _backup_dir() -> Path:
    return Path(settings.MEDIA_ROOT) / "coop" / "backups"


def _make_payment(member) -> Payment:
    now = timezone.now()
    return Payment.objects.create(
        member=member,
        montant=Decimal("1500.00"),
        type=Payment.Type.EPARGNE,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        date_versement=now,
        date_validation=now,
    )


def test_backup_writes_jsonl_with_manifest_and_rows(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    member = MemberFactory()
    _make_payment(member)

    call_command("backup_ecritures")

    today = timezone.localdate().isoformat()
    out = _backup_dir() / f"ecritures_{today}.jsonl.gz"
    assert out.exists(), "le fichier de backup du jour doit être créé"

    with gzip.open(out, "rt", encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]

    assert lines, "le backup ne doit pas être vide"
    manifest = lines[0]
    assert manifest.get("_manifest") is True
    assert "payments.Payment" in manifest["models"]
    # Au moins l'écriture Payment créée doit figurer dans le dump.
    payment_rows = [r for r in lines[1:] if r.get("model") == "payments.payment"]
    assert len(payment_rows) >= 1
    assert payment_rows[0]["fields"]["montant"] == "1500.00"


def test_backup_is_non_destructive(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    member = MemberFactory()
    _make_payment(member)
    before = Payment.objects.count()

    call_command("backup_ecritures")

    assert Payment.objects.count() == before, "un backup ne doit RIEN supprimer"


def test_dry_run_writes_no_file(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    member = MemberFactory()
    _make_payment(member)

    call_command("backup_ecritures", dry_run=True)

    today = timezone.localdate().isoformat()
    out = _backup_dir() / f"ecritures_{today}.jsonl.gz"
    assert not out.exists(), "le dry-run ne doit écrire aucun fichier"


def test_retention_prunes_old_backups(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    member = MemberFactory()
    _make_payment(member)

    backup_dir = _backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stale = backup_dir / "ecritures_2000-01-01.jsonl.gz"
    stale.write_bytes(b"stale")
    # Recule la mtime bien au-delà de la fenêtre de rétention.
    old = time.time() - 200 * 86400
    import os
    os.utime(stale, (old, old))

    call_command("backup_ecritures", retention=90)

    assert not stale.exists(), "un backup plus vieux que la rétention doit être purgé"
