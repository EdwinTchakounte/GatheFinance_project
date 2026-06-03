"""Backfill ``Member.date_derniere_reinscription`` (A2).

Tous les membres existants héritent de ``date_adhesion`` comme première
référence pour le calcul de l'anniversaire annuel. Si un membre n'a pas
de date d'adhésion (cas pathologique), on saute — ``prochaine_reinscription_due``
renverra alors ``None`` et le cron ignorera la ligne.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    Member = apps.get_model("members", "Member")
    for m in Member.objects.filter(
        date_derniere_reinscription__isnull=True
    ).only("id", "date_adhesion"):
        if m.date_adhesion is None:
            continue
        m.date_derniere_reinscription = m.date_adhesion
        m.save(update_fields=["date_derniere_reinscription"])


def backwards(apps, _schema_editor):
    Member = apps.get_model("members", "Member")
    Member.objects.all().update(date_derniere_reinscription=None)


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0006_member_date_derniere_reinscription"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
