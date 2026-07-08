"""
Base settings shared by all environments.

Environment-specific settings live in dev.py / prod.py.
Secrets and per-environment values come from environment variables (see .env.example).
"""
from pathlib import Path

import environ

# backend/config/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = BASE_DIR / "config"

env = environ.Env()
# Read backend/.env if present (dev convenience; in prod, real env vars take precedence).
environ.Env.read_env(BASE_DIR / ".env")

# --- Core -------------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Public base URL of this backend (used to build absolute media/API URLs).
WAGTAILADMIN_BASE_URL = env("WAGTAILADMIN_BASE_URL", default="http://localhost:8000")

# Internal base URL of the Next.js front-end (server-to-server: revalidation
# webhook depuis le backend Docker → frontend Docker, par DNS interne).
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:3000")

# Public base URL of the Next.js front-end (vue du navigateur de l'utilisateur :
# liens "Voir sur le site" depuis l'admin Wagtail, redirections serve(), etc.).
# En dev local sans Docker, c'est la même que FRONTEND_BASE_URL ; avec Docker
# où le backend voit le frontend en `http://frontend:3000`, il faut overrider.
FRONTEND_PUBLIC_URL = env("FRONTEND_PUBLIC_URL", default=FRONTEND_BASE_URL)

# Public base URL of THIS backend (used to construct the webHookUrl we hand
# to payment providers). Must be reachable from Tara — in dev with Docker we
# expose port 8200 via ngrok / cloudflared and put the tunnel URL here.
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="http://localhost:8200")

# Secret shared with the front-end to authenticate the on-demand revalidation webhook.
REVALIDATE_SECRET = env("REVALIDATE_SECRET", default="dev-revalidate-secret")

# --- Payment providers ------------------------------------------------------
# Each provider reads its own env vars; leave them blank in dev/CI so any
# accidental call fails loud (`ProviderError: credentials not configured`).

# Tara Money — https://taramoney.com/developer
TARA_API_KEY = env("TARA_API_KEY", default="")
TARA_BUSINESS_ID = env("TARA_BUSINESS_ID", default="")
TARA_WEBHOOK_SECRET = env("TARA_WEBHOOK_SECRET", default="")

# Mode "test paiements auto-validés" — recette des flows métier de bout en
# bout sans dépendre du webhook Tara. Quand True :
#   • POST /payments/init/        → Payment créé puis IMMÉDIATEMENT validé
#     (hook `_hook_*` joué, solde épargne crédité, échéances imputées, etc.)
#   • payout MOMO (retrait épargne) → idem côté décaissement, WithdrawalRequest
#     passe direct EN_PAYOUT → COMPLETEE.
# À NE JAMAIS activer en prod : voir ``PAYMENTS_TEST_AUTO_VALIDATE`` dans
# `.env.prod`. Validé par défaut False, pousser à True via env uniquement
# sur les environnements de recette/staging.
PAYMENTS_TEST_AUTO_VALIDATE = env.bool("PAYMENTS_TEST_AUTO_VALIDATE", default=False)

# Mode test STK Push réel — autorise un montant arbitraire (>= 100 XAF) pour
# tester les pop-ups MTN/Orange depuis le mobile sans payer le tarif réel
# (1000 XAF carnet, frais d'étude variables, dépôts épargne classique mini, etc.).
# Quand True :
#   • cfg.depot_min / depot_max épargne classique → bypass
#   • cotisation multi-jours `nb_jours * min_per_day` → bypass
# Le serializer impose toujours `montant >= 100`. À NE JAMAIS activer en prod.
# TODO: REMOVE_FOR_PROD — flag temporaire période de test.
PAYMENTS_TEST_ALLOW_ANY_AMOUNT = env.bool(
    "PAYMENTS_TEST_ALLOW_ANY_AMOUNT", default=False
)

# --- Applications -----------------------------------------------------------

INSTALLED_APPS = [
    # CMS apps (public site, Wagtail-backed)
    "apps_cms.core",
    "apps_cms.content",
    "apps_cms.cms",
    "apps_cms.forms",
    # Cooperative business apps (espace membre + dashboard admin)
    "apps_coop.members",
    "apps_coop.savings",
    "apps_coop.loans",
    "apps_coop.payments",
    "apps_coop.notifications",
    "apps_coop.audit",
    "apps_coop.forms",
    "apps_coop.social",
    # Wagtail
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.settings",
    "wagtail.contrib.styleguide",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail.api.v2",
    "wagtail",
    "wagtail_localize",
    "wagtail_localize.locales",  # replaces wagtail.locales
    "modelcluster",
    "taggit",
    # Third-party
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "django_q",
    "anymail",
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise is inserted here in prod.py for static-file serving.
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # RBAC — enforcement des ressources admin (après auth, request.user résolu).
    "apps_coop.members.rbac_middleware.RBACResourceMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    # Cooperative audit log — must run last so request.user is resolved.
    "apps_coop.audit.middleware.AuditMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PROJECT_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wagtail.contrib.settings.context_processors.settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database ---------------------------------------------------------------
# Dedicated database for the site/CMS. Strictly separate from the cooperative
# application's financial database.

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    ),
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Password validation ----------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internationalisation ---------------------------------------------------
# French is the default; English is the secondary locale. The Next.js front
# serves FR at "/" and EN at "/en"; Wagtail manages the FR/EN content
# translations via wagtail-localize.

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("fr", "Français"),
    ("en", "English"),
]
WAGTAIL_CONTENT_LANGUAGES = LANGUAGES
WAGTAIL_I18N_ENABLED = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# --- Static & media ---------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [PROJECT_DIR / "static"] if (PROJECT_DIR / "static").exists() else []

# Local filesystem by default; Backblaze B2 (S3-compatible) is wired in prod.py
# when the relevant env vars are set.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# --- Email (Brevo via API HTTP / django-anymail) ----------------------------
# Dev : backend console (les e-mails s'affichent dans les logs).
# Prod : prod.py bascule sur le backend Anymail-Brevo (API HTTP transactionnelle,
# PAS de SMTP). La clé API Brevo est lue depuis l'env (BREVO_API_KEY).
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
ANYMAIL = {
    "BREVO_API_KEY": env("BREVO_API_KEY", default=""),
}
# --- Push notifications (bases FCM/APNs) ------------------------------------
# Tant qu'aucune de ces valeurs n'est fournie, l'envoi push est un no-op loggé
# (voir apps_coop/notifications/push.py). À renseigner quand FCM sera branché.
FCM_SERVER_KEY = env("FCM_SERVER_KEY", default="")
FCM_CREDENTIALS_JSON = env("FCM_CREDENTIALS_JSON", default="")

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Gathé Finance <noreply@horus-lab.com>")
# Inbox that receives contact messages / membership requests.
CONTACT_NOTIFICATION_EMAIL = env(
    "CONTACT_NOTIFICATION_EMAIL", default="contact@gathe-finance.com"
)

# --- REST framework ---------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    # Session auth for portal/admin (cookies HttpOnly + CSRF); BasicAuth kept
    # in dev for DRF browsable API. Add JWT later for mobile, scoped separately.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/hour",
        "user": "1000/hour",
        "form-submit": "10/hour",
        "auth-login": "20/hour",
        # Mot de passe oublié — 5/h/IP suffit (cas réels rares + anti-bruteforce).
        "auth-password-reset": "5/hour",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}


# --- Scheduler (django-q2, ORM broker — no Redis) ---------------------------
# Runs in a separate worker process (``python manage.py qcluster``). Schedules
# are stored in ``django_q_schedule``; admin can pause/edit them from Django
# admin. Three schedules are seeded via ``manage.py seed_q_schedules``.

Q_CLUSTER = {
    "name": "gathe-coop",
    "workers": 2,
    "recycle": 500,
    "timeout": 300,
    "retry": 360,
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",   # use the Django DB as broker
    "catch_up": False,  # don't replay missed schedules after downtime
    "ack_failures": True,
}


# --- OpenAPI / Swagger ------------------------------------------------------

SPECTACULAR_SETTINGS = {
    "TITLE": "Gathe Finance — API coopérative",
    "DESCRIPTION": (
        "API REST de la plateforme Gathe Finance.\n\n"
        "**Surfaces** :\n"
        "- `/api/v1/auth/*` — authentification session (cookies HttpOnly + CSRF)\n"
        "- `/api/v1/members/*` — membre connecté\n"
        "- `/api/v1/savings/*` — compte d'épargne\n"
        "- `/api/v1/loans/*` — crédits et demandes\n"
        "- `/api/v1/payments/*` — paiements Mobile Money (Tara)\n\n"
        "L'API CMS publique (`/api/v2/*` Wagtail, `/api/forms/*`) est exposée séparément "
        "et n'est pas documentée ici."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    # Skip Wagtail admin/public APIs from the schema — keep it focused on the coop.
    "PREPROCESSING_HOOKS": [
        "config.api_schema_hooks.keep_only_coop_paths",
    ],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "displayOperationId": False,
        "persistAuthorization": True,
        "docExpansion": "list",
    },
    "TAGS": [
        {"name": "auth", "description": "Authentification session + CSRF."},
        {"name": "members", "description": "Membres connectés."},
        {"name": "savings", "description": "Compte d'épargne du membre."},
        {"name": "loans", "description": "Demandes de crédit, crédits actifs, échéancier."},
        {"name": "payments", "description": "Paiements Mobile Money via Tara."},
    ],
}

# --- CORS -------------------------------------------------------------------
# Two surfaces talk to this backend from a browser:
#   1. Public site (vitrine)         — read-only API calls, no credentials
#   2. Portal & admin (authenticated) — session cookies, CSRF tokens
#
# `CORS_ALLOW_CREDENTIALS = True` is required for the portal/admin to send the
# session cookie cross-origin. In prod the origins are restricted to the actual
# subdomains (app.gathe-finance.com, admin.gathe-finance.com).

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3200",
        "http://127.0.0.1:3200",
    ],
)
CORS_ALLOW_CREDENTIALS = True

# --- Wagtail ----------------------------------------------------------------

WAGTAIL_SITE_NAME = "Gathe Finance"
WAGTAILDOCS_EXTENSIONS = ["csv", "docx", "key", "odt", "pdf", "pptx", "rtf", "txt", "xlsx", "zip"]
# Headless API: allow larger result pages (the front-end fetches blog lists at build time).
WAGTAILAPI_LIMIT_MAX = 100
# Allow translating pages/snippets via the wagtail-localize workflow.
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = None  # plug a translator later if desired

# Search backend (DB by default; can be swapped for a dedicated engine later).
WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
    }
}

# --- Security (sane defaults; tightened further in prod.py) ------------------

# SAMEORIGIN (pas DENY) pour permettre les <iframe> de prévisualisation PDF
# / images servies via /media/* (BRC, flyers campagne, règlement intérieur)
# depuis l'admin Next.js qui proxifie /media/* vers le backend. Les contenus
# restent non-iframable depuis une origine tierce — sécurité préservée.
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_CONTENT_TYPE_NOSNIFF = True

# Session cookies — HttpOnly always, Secure in prod (overridden in prod.py),
# SameSite=Lax to allow same-origin top-level navigation while blocking
# cross-site POSTs that don't carry the CSRF token.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_NAME = "gathe_sessionid"
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 h — staff and members re-login daily
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# CSRF — cookie readable by JS so the SPA can attach the X-CSRFToken header.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = False
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["http://localhost:3000", "http://localhost:3200"],
)

# --- Logging ----------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
