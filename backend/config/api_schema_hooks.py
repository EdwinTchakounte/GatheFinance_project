"""drf-spectacular hooks — narrow the schema to the cooperative API.

By default the schema also captures Wagtail admin API routes (cf. ``/admin/api/*``)
because they use DRF too. Filter to ``/api/v1/*`` (business API) and
``/api/forms/*`` (public form intake) so the Swagger UI stays focused.
"""
from __future__ import annotations


ALLOWED_PREFIXES = ("/api/v1/", "/api/forms/")


def keep_only_coop_paths(endpoints, **kwargs):
    """Pre-processing hook used by ``SPECTACULAR_SETTINGS.PREPROCESSING_HOOKS``."""
    return [e for e in endpoints if e[0].startswith(ALLOWED_PREFIXES)]
