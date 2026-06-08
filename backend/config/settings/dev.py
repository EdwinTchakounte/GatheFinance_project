"""Development settings."""
from .base import *  # noqa: F401,F403
from .base import INSTALLED_APPS, MIDDLEWARE, env

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-not-for-production")  # noqa: S105
ALLOWED_HOSTS = ["*"]

# Show e-mails in the console during development unless overridden.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

# IMPORTANT — Ne PAS utiliser CORS_ALLOW_ALL_ORIGINS=True ici : le spec CORS
# interdit Access-Control-Allow-Origin: * en présence de credentials, et
# django-cors-headers retire alors silencieusement l'entête
# Access-Control-Allow-Credentials. Conséquence : le navigateur refuse de
# poser le cookie de session → F5 = reconnexion. Liste explicite des origines
# dev (portail + admin + vitrine, ports natifs et overrides locaux).
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        # Vitrine / portail / admin sur ports natifs
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Vitrine / portail / admin sur ports overrides (.env local : 3200/3201/3202)
        "http://localhost:3200",
        "http://127.0.0.1:3200",
        "http://localhost:3201",
        "http://127.0.0.1:3201",
        "http://localhost:3202",
        "http://127.0.0.1:3202",
    ],
)
# Accès LAN dev : autoriser n'importe quelle IP privée 10.x.x.x / 192.168.x.x
# / 172.16-31.x.x sur les ports vitrine/portail/admin (3200-3299). Permet
# d'ouvrir le portail/admin depuis un téléphone connecté au même wifi sans
# devoir ajouter manuellement l'IP du poste à chaque fois (DHCP change).
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://10\.\d{1,3}\.\d{1,3}\.\d{1,3}:32\d{2}$",
    r"^http://192\.168\.\d{1,3}\.\d{1,3}:32\d{2}$",
    r"^http://172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}:32\d{2}$",
]

INTERNAL_IPS = ["127.0.0.1"]

# debug-toolbar / django-extensions are optional dev conveniences.
try:
    import debug_toolbar  # noqa: F401

    INSTALLED_APPS = INSTALLED_APPS + ["debug_toolbar"]
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]
except ImportError:  # pragma: no cover
    pass

try:
    import django_extensions  # noqa: F401

    INSTALLED_APPS = INSTALLED_APPS + ["django_extensions"]
except ImportError:  # pragma: no cover
    pass
