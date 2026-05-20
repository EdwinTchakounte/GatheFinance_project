from django.apps import AppConfig


class CmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps_cms.cms"
    label = "cms"
    verbose_name = "Pages du site"

    def ready(self):
        from wagtail.signals import page_published, page_unpublished

        from . import signals

        page_published.connect(signals.on_page_published, dispatch_uid="cms_revalidate_published")
        page_unpublished.connect(signals.on_page_unpublished, dispatch_uid="cms_revalidate_unpublished")

