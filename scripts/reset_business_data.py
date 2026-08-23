"""Purge des DONNÉES MÉTIER GATHE Finance (membres, crédits, campagnes,
collectes, épargne, transactions, support, social, notifications, audit).

CONSERVE toute la CONFIG et les comptes admin :
  - AppSetting, FeeType, RateParam, FormSchema, StaffRole
  - LoanDurationTier, PaymentModalityConfig, ClassicSavingsConfig
  - EmailTemplate, EventConfig, EventHook, CooperativeAsset, BlockedIP
  - Pages Wagtail / vitrine (intactes)
  - Comptes User is_staff / is_superuser (admins, comité)

Sécurité : DRY-RUN par défaut (compte seulement, ne supprime rien).
Pour exécuter réellement, poser la variable d'env  GATHE_WIPE_CONFIRM=YES .
Tout tourne dans UNE transaction : la moindre erreur => rollback total (0 dégât).

Usage (dans le conteneur backend) :
    python manage.py shell < reset_business_data.py                 # dry-run
    GATHE_WIPE_CONFIRM=YES python manage.py shell < reset_business_data.py  # réel
"""

import os

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.deletion import ProtectedError

from apps_coop.social.models import ContentComment, ContentReaction
from apps_coop.support.models import SupportMessage, SupportThread
from apps_coop.notifications.models import (
    Announcement,
    DeviceToken,
    EmailLog,
    Notification,
    NotificationPreference,
)
from apps_coop.loans.models import (
    AvalisteConsent,
    CampaignApplication,
    CampaignApplicationDocument,
    JudicialEscalation,
    LenderAllocation,
    LenderConsentRequest,
    LenderInterestPayout,
    Loan,
    LoanFundingRequest,
    LoanGuarantee,
    LoanInstallment,
    LoanRenewal,
    LoanRepayment,
    LoanRequest,
    MicrocreditCampaign,
)
from apps_coop.payments.models import Payment, PaymentProof
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    LenderConsent,
    LenderTranche,
    SavingsAccount,
    SavingsTransaction,
    WithdrawalRequest,
)
from apps_coop.special_collections.models import (
    SpecialCollectionCycle,
    SpecialCollectionMembership,
    SpecialCollectionTransaction,
)
from apps_coop.members.models import (
    BRCDocument,
    BookletOrder,
    Document,
    Member,
    MembershipRequest,
    PasswordResetCode,
    PasswordSetupToken,
)
from apps_coop.audit.models import AuditLog

User = get_user_model()
CONFIRM = os.environ.get("GATHE_WIPE_CONFIRM") == "YES"

# Ordre STRICT enfants -> parents (chaque delete cascade ce qui est CASCADE).
ORDER = [
    # social / support / notifications
    ContentReaction, ContentComment,
    SupportMessage, SupportThread,
    Notification, EmailLog, DeviceToken, NotificationPreference, Announcement,
    # crédits : enfants
    LoanRepayment, LoanInstallment, LoanRenewal,
    LenderInterestPayout, LenderConsentRequest, LoanFundingRequest, LenderAllocation,
    AvalisteConsent, LoanGuarantee, JudicialEscalation,
    CampaignApplicationDocument, CampaignApplication,
    # crédits : coeur puis campagnes
    LoanRequest, Loan, MicrocreditCampaign,
    # épargne
    LenderTranche, LenderConsent, WithdrawalRequest,
    ClassicSavingsTransaction, SavingsTransaction,
    ClassicSavingsAccount, SavingsAccount,
    # collectes particulières
    SpecialCollectionTransaction, SpecialCollectionMembership, SpecialCollectionCycle,
    # paiements
    PaymentProof, Payment,
    # membres : pièces puis Member
    BRCDocument, BookletOrder, Document, MembershipRequest,
    PasswordResetCode, PasswordSetupToken,
    Member,
    # journal d'audit
    AuditLog,
]

# Comptes de login à supprimer = ceux liés à un membre, JAMAIS un admin.
member_user_ids = list(Member.objects.values_list("user_id", flat=True))
purge_users = User.objects.filter(
    id__in=member_user_ids, is_superuser=False, is_staff=False
)

print("=" * 60)
print("COMPTAGE AVANT (données métier)")
print("=" * 60)
for m in ORDER:
    print(f"  {m.__name__:34} {m.objects.count():>8}")
print(f"  {'User (membres, non-admin)':34} {purge_users.count():>8}")
print("-" * 60)
print(
    f"  CONSERVÉS : {User.objects.filter(is_superuser=True).count()} superuser(s), "
    f"{User.objects.filter(is_staff=True).count()} staff, "
    f"{User.objects.exclude(id__in=member_user_ids).count()} comptes non-membres"
)
print("=" * 60)

if not CONFIRM:
    print("\n*** DRY-RUN — RIEN N'A ÉTÉ SUPPRIMÉ ***")
    print("Pour exécuter : relance avec  GATHE_WIPE_CONFIRM=YES  devant la commande.")
else:
    # Suppression résiliente : on retente en plusieurs passes les modèles encore
    # protégés par une FK PROTECT (ex. Loan.loan_request). Chaque delete tourne
    # dans un SAVEPOINT (atomic imbriqué) : un ProtectedError annule ce seul
    # savepoint sans casser la transaction externe (indispensable sous Postgres).
    with transaction.atomic():
        remaining = list(ORDER)
        for pass_no in range(1, 12):
            still = []
            progressed = False
            for m in remaining:
                try:
                    with transaction.atomic():  # savepoint
                        n, _ = m.objects.all().delete()
                    if n:
                        progressed = True
                        print(f"  supprimé {m.__name__:34} {n:>8}")
                except ProtectedError:
                    still.append(m)  # dépend d'un modèle encore présent → passe suivante
            remaining = still
            if not remaining:
                break
            if not progressed:
                raise RuntimeError(
                    f"Blocage après passe {pass_no} — non supprimables : "
                    f"{[x.__name__ for x in remaining]}"
                )
        n, _ = purge_users.delete()
        print(f"  supprimé {'User (membres)':34} {n:>8}")
    print("\n" + "=" * 60)
    print("TERMINÉ — données métier purgées, config + comptes admin conservés.")
    print("=" * 60)
