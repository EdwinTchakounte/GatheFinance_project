"""CH-4 — Services côté soumission de formulaires dynamiques.

L'idée : un endpoint métier (POST /forms/adhesion/, POST /loans/, etc.) appelle
``apply_form_schema()`` AVANT de créer son modèle. La fonction :

1. Récupère le schéma actif du ``kind`` demandé (ou None → mode legacy).
2. Évalue les conditions de visibilité par rapport au payload reçu.
3. Valide les `required` côté serveur (sécurité : le portail peut tricher).
4. Split le payload en :
     • ``hardcoded_kwargs`` — clés qui appartiennent aux colonnes du modèle
     • ``extra_payload``   — clés ajoutées par l'admin via FormSchema
5. Renvoie aussi la ``form_schema_version`` à poser sur le modèle.

Le caller fait ensuite ``Model.objects.create(**hardcoded_kwargs,
extra_payload=extra_payload, form_schema_version=version)``.

Mode legacy : si aucun schéma actif (ou ``kind=None``), le helper se met en
mode bypass — il retourne le payload tel quel comme `hardcoded_kwargs`,
`extra_payload={}` et `version=None`. Les anciens endpoints continuent donc
de fonctionner sans changement.
"""
from __future__ import annotations

from typing import Any, Iterable
from rest_framework import serializers

from .models import FormSchema


def _is_visible(field: dict, payload: dict[str, Any]) -> bool:
    cond = field.get("condition")
    if not cond:
        return True
    ref = payload.get(cond["field"])
    op = cond.get("operator")
    val = cond.get("value")
    if op == "equals":
        return ref == val
    if op == "not_equals":
        return ref != val
    if op == "in":
        return isinstance(val, (list, tuple)) and ref in val
    return True


def _iter_fields(schema: dict) -> Iterable[dict]:
    for section in (schema or {}).get("sections", []) or []:
        for field in section.get("fields", []) or []:
            yield field


def apply_form_schema(
    kind: str,
    payload: dict[str, Any],
    *,
    hardcoded_keys: set[str],
) -> tuple[dict[str, Any], dict[str, Any], int | None]:
    """Sépare ``payload`` selon le ``FormSchema`` actif du ``kind`` donné.

    Args:
      kind: clé ``FormSchema.Kind`` (ex. "adhesion").
      payload: payload (déjà désérialisé par DRF) issu de la requête membre.
      hardcoded_keys: noms de colonnes Django existantes — toute clé qui matche
        atterrit dans le 1er dict (kwargs du modèle) au lieu de extra_payload.

    Returns:
      (hardcoded_kwargs, extra_payload, form_schema_version)
      - ``form_schema_version`` est None si aucun schéma actif (mode legacy).
      - Soulève ``serializers.ValidationError`` si un champ visible et required
        est absent du payload, ou si une valeur inconnue circule (clé non
        prévue dans le schéma actif).
    """
    schema_row = FormSchema.objects.filter(kind=kind, is_active=True).first()
    if schema_row is None:
        # Mode legacy : pas de schéma actif → bypass total.
        kwargs = {k: v for k, v in payload.items() if k in hardcoded_keys}
        return kwargs, {}, None

    schema = schema_row.schema or {}
    known_ids = {f["id"] for f in _iter_fields(schema)}

    # 1. Required côté serveur — UNIQUEMENT pour les champs visibles ajoutés
    # via FormSchema (non-hardcoded). Les hardcoded sont validés par le
    # serializer DRF du caller, c'est sa responsabilité.
    errors: dict[str, str] = {}
    for field in _iter_fields(schema):
        if field["id"] in hardcoded_keys:
            continue
        if not _is_visible(field, payload):
            continue
        # Les champs FICHIER sont uploadés hors-bande (endpoint attachments)
        # APRÈS la création de l'objet — ils ne sont donc jamais présents dans
        # le payload de création. Ne pas les exiger ici : sinon toute demande
        # avec un champ file requis (ex. preuve CGA/CFP quand la réponse est
        # « oui ») lèverait une ValidationError → bascule legacy → extra_payload
        # vidé (la déclaration « oui » serait silencieusement perdue).
        if field.get("type") == "file":
            continue
        if field.get("required"):
            val = payload.get(field["id"])
            if val is None or val == "" or (isinstance(val, (list, tuple)) and len(val) == 0):
                errors[field["id"]] = "Ce champ est obligatoire."
    if errors:
        raise serializers.ValidationError(errors)

    # 2. Split.
    hardcoded_kwargs: dict[str, Any] = {}
    extra: dict[str, Any] = {}
    for key, val in payload.items():
        if key not in known_ids:
            # Champ non déclaré dans le schéma → ignoré silencieusement (pour
            # rester rétro-compatible avec un client qui enverrait des extras
            # comme captcha, honeypot, etc. — c'est au caller de les filtrer).
            continue
        # On respecte les conditions de visibilité côté serveur : si un champ
        # n'est pas visible, on ne l'inscrit pas (sinon un client malicieux
        # pourrait poser un champ caché).
        field_def = next((f for f in _iter_fields(schema) if f["id"] == key), None)
        if field_def is not None and not _is_visible(field_def, payload):
            continue
        # Les champs FICHIER (preuves BRC, titres…) ne vont JAMAIS dans
        # extra_payload : ils ne sont pas JSON-sérialisables (crash 500) et sont
        # stockés comme Documents via l'endpoint attachments. On les ignore ici,
        # que la valeur soit un fichier uploadé inline ou déclarée type=file.
        if (field_def is not None and field_def.get("type") == "file") or hasattr(val, "read"):
            continue

        if key in hardcoded_keys:
            hardcoded_kwargs[key] = val
        else:
            extra[key] = val

    return hardcoded_kwargs, extra, schema_row.version
