"""On-demand ISR revalidation: ping the Next.js front-end when content changes.

When a page is published/unpublished (or a tracked snippet changes), POST the
affected path(s) to the front-end's revalidation webhook so it regenerates the
corresponding static pages. The webhook is authenticated with REVALIDATE_SECRET.
"""
import json
import logging
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


def _post_revalidate(paths: list[str]) -> None:
    if not paths:
        return
    base = (settings.FRONTEND_BASE_URL or "").rstrip("/")
    if not base:
        return
    url = f"{base}/api/revalidate"
    body = json.dumps({"paths": paths}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Revalidate-Secret": settings.REVALIDATE_SECRET,
        },
    )
    try:
        urllib.request.urlopen(req, timeout=3)  # noqa: S310 - fixed, trusted URL
    except Exception as exc:  # noqa: BLE001 - best effort; must never break publishing
        logger.warning("Revalidation webhook failed for %s: %s", paths, exc)


def _page_paths(page) -> list[str]:
    """Best-effort mapping of a Wagtail page to front-end paths to revalidate."""
    try:
        url_path = page.get_url_parts()[2]  # e.g. "/" or "/blog/some-post/"
    except Exception:  # noqa: BLE001
        return []
    locale = getattr(getattr(page, "locale", None), "language_code", "fr")
    prefix = "" if locale == "fr" else f"/{locale}"
    paths = {f"{prefix}{url_path}".rstrip("/") or "/"}
    # A new/updated post also affects the blog index and the home page.
    if page.specific_class and page.specific_class.__name__ == "BlogPostPage":
        paths.add(f"{prefix}/blog".rstrip("/") or "/")
        paths.add(prefix or "/")
    return list(paths)


def on_page_published(sender, instance, **kwargs):  # noqa: ARG001
    _post_revalidate(_page_paths(instance))


def on_page_unpublished(sender, instance, **kwargs):  # noqa: ARG001
    _post_revalidate(_page_paths(instance))
