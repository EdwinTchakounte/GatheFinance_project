"""Helpers internes — resolution des cibles (article / campagne) → ContentType.

On factorise ici la logique "donne-moi le ContentType + objet existant
pour un kind donne", utilisee par toutes les vues membres et admin.

Choix : on n'importe **pas** les modeles directement au top-level pour
eviter les cycles entre apps_coop.social et apps_cms.cms / apps_coop.loans.
On resout via `django.apps.apps.get_model(...)` au runtime.
"""
from __future__ import annotations

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.http import Http404


# Cles publiques utilisees dans les URLs et l'API (article|campaign).
# Chaque cle pointe vers (app_label, model_name) — modifies en un seul
# endroit si on veut ajouter un nouveau type de cible.
TARGET_KINDS: dict[str, tuple[str, str]] = {
    "article": ("cms", "BlogPostPage"),
    "campaign": ("loans", "MicrocreditCampaign"),
}


def get_content_type_for_kind(kind: str) -> ContentType:
    """Renvoie le `ContentType` pour `article` ou `campaign`.

    Leve `Http404` si le kind est inconnu — l'URL routing n'en cree
    normalement jamais d'autre que ceux listes ci-dessus, mais on
    durcit l'API admin qui accepte `?content_type=` libre.
    """
    if kind not in TARGET_KINDS:
        raise Http404("Type de contenu inconnu.")
    app_label, model_name = TARGET_KINDS[kind]
    model = apps.get_model(app_label, model_name)
    return ContentType.objects.get_for_model(model)


def get_target_or_404(kind: str, object_id: int):
    """Renvoie l'instance ciblee (article ou campagne) ou 404.

    On valide explicitement que l'objet existe avant de creer un like /
    commentaire, sinon on accumulerait des GenericFK orphelines au moindre
    typo client.
    """
    ct = get_content_type_for_kind(kind)
    model_cls = ct.model_class()
    if model_cls is None:
        raise Http404("Modele cible introuvable.")
    try:
        return ct, model_cls.objects.get(pk=object_id)
    except model_cls.DoesNotExist as exc:  # pragma: no cover — chemin defensif
        raise Http404("Contenu introuvable.") from exc
