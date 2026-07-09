"""Idempotent bootstrap of the site's CMS content.

Ensures the FR/EN locales exist, that a `cms.HomePage` is the root of the
default Wagtail site, that the blog index and the two legal pages exist, and
that the site-wide settings rows are created. Safe to run on every deploy
(see backend/docker-entrypoint.sh).
"""
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from wagtail.models import Locale, Page, Site

from apps_cms.cms.models import BlogIndexPage, HomePage, LegalPage
from apps_cms.core.models import SeoSettings, SiteSettings


class Command(BaseCommand):
    help = "Create the FR/EN locales, the default HomePage / Blog / legal pages and the site settings (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        fr, _ = Locale.objects.get_or_create(language_code="fr")
        en, en_created = Locale.objects.get_or_create(language_code="en")
        self.stdout.write(f"Locales: fr (id={fr.pk}), en (id={en.pk}){' [created]' if en_created else ''}")

        root = Page.get_first_root_node()
        site = Site.objects.filter(is_default_site=True).first()

        home = HomePage.objects.first()
        if home is None:
            home = HomePage(
                title="GATHE Finance",
                slug="accueil",
                locale=fr,
                seo_title="GATHE Finance — Coopérative d'épargne et de crédit au Cameroun",
                search_description=(
                    "Coopérative d'épargne et de crédit des entrepreneurs camerounais : crédit, "
                    "épargne, transferts, investissement communautaire et éducation financière."
                ),
            )
            root.add_child(instance=home)
            home.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"Created HomePage (id={home.pk})"))

        # Make the default site point at our HomePage and drop the auto-generated
        # "Welcome to Wagtail" placeholder page if it is still around.
        if site and site.root_page_id != home.pk:
            old_root = site.root_page
            site.root_page = home
            site.save(update_fields=["root_page"])
            self.stdout.write("Repointed default Site → HomePage")
            generic_page_ct = ContentType.objects.get_for_model(Page)
            if (
                old_root
                and old_root.pk != home.pk
                and old_root.content_type_id == generic_page_ct.id
                and not old_root.get_children().exists()
            ):
                old_root.delete()
                self.stdout.write("Removed the default placeholder page")
        elif not site:
            Site.objects.create(hostname="localhost", port=80, root_page=home, is_default_site=True, site_name="GATHE Finance")
            self.stdout.write("Created default Site → HomePage")

        # Child pages: blog index + legal pages.
        if not BlogIndexPage.objects.child_of(home).exists():
            blog = BlogIndexPage(title="Blog", slug="blog", locale=fr)
            home.add_child(instance=blog)
            blog.save_revision().publish()
            self.stdout.write(self.style.SUCCESS(f"Created BlogIndexPage (id={blog.pk})"))

        for title, slug in (
            ("Mentions légales", "mentions-legales"),
            ("Politique de confidentialité", "politique-confidentialite"),
        ):
            if not LegalPage.objects.child_of(home).filter(slug=slug).exists():
                page = LegalPage(title=title, slug=slug, locale=fr)
                home.add_child(instance=page)
                page.save_revision().publish()
                self.stdout.write(self.style.SUCCESS(f"Created LegalPage '{slug}' (id={page.pk})"))

        # Site-wide settings (defaults come from the model fields).
        SiteSettings.load(request_or_site=site)
        SeoSettings.load(request_or_site=site)

        # Headless : aligne Site.hostname/port sur la vitrine Next.js publique
        # pour que `page.full_url` (utilisé par "Voir sur le site") pointe sur
        # le frontend et non sur Wagtail lui-même.
        public = getattr(settings, "FRONTEND_PUBLIC_URL", None) or settings.FRONTEND_BASE_URL
        parsed = urlparse(public)
        if parsed.hostname:
            site = Site.objects.filter(is_default_site=True).first()
            if site:
                new_port = parsed.port or (443 if parsed.scheme == "https" else 80)
                changed = []
                if site.hostname != parsed.hostname:
                    site.hostname = parsed.hostname
                    changed.append("hostname")
                if site.port != new_port:
                    site.port = new_port
                    changed.append("port")
                if changed:
                    site.save(update_fields=changed)
                    self.stdout.write(
                        f"Site repointed → {parsed.hostname}:{new_port} (updated {', '.join(changed)})"
                    )

        self.stdout.write(self.style.SUCCESS("Site settings ensured. Bootstrap complete."))
