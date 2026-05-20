"""Expose inbound form data in the Wagtail admin (consultation by the client).

Grouped under a "Messages & demandes" menu item. Editors can browse, inspect and
update the status of submissions; creation/deletion is left to administrators.
"""
from wagtail import hooks
from wagtail.admin.viewsets.model import ModelViewSet, ModelViewSetGroup

from .models import ContactSubmission, NewsletterSubscriber

# NOTE: MembershipRequest has migrated to apps_coop.members. Adhesion requests
# are now instructed from the Django admin (`/django-admin/members/membershiprequest/`)
# — that workflow creates the User + Member + SavingsAccount atomically, which
# is out of scope for a Wagtail snippet.


class ContactSubmissionViewSet(ModelViewSet):
    model = ContactSubmission
    icon = "mail"
    menu_label = "Messages de contact"
    list_display = ("name", "email", "city", "status", "submitted_at")
    list_filter = ("status", "language", "submitted_at")
    search_fields = ("name", "email", "city", "message")
    form_fields = ("status", "internal_notes")
    inspect_view_enabled = True


class NewsletterSubscriberViewSet(ModelViewSet):
    model = NewsletterSubscriber
    icon = "mail"
    menu_label = "Inscrits newsletter"
    list_display = ("email", "language", "is_active", "source", "subscribed_at")
    list_filter = ("is_active", "language", "subscribed_at")
    search_fields = ("email",)
    form_fields = ("is_active",)
    inspect_view_enabled = True


class SubmissionsGroup(ModelViewSetGroup):
    menu_label = "Messages & demandes"
    menu_icon = "mail"
    menu_order = 250
    items = (ContactSubmissionViewSet, NewsletterSubscriberViewSet)


@hooks.register("register_admin_viewset")
def register_submissions_group():
    return SubmissionsGroup()
