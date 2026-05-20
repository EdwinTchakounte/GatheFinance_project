"""Development settings."""
from .base import *  # noqa: F401,F403
from .base import INSTALLED_APPS, MIDDLEWARE, env

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-not-for-production")  # noqa: S105
ALLOWED_HOSTS = ["*"]

# Show e-mails in the console during development unless overridden.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

# Allow any localhost origin to call the API while developing.
CORS_ALLOW_ALL_ORIGINS = True

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
