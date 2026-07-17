# syntax=docker/dockerfile:1
# ---- Backend: Django + Wagtail (CMS headless) -------------------------------
# Multi-stage. `dev` target = autoreload server; `prod` target = gunicorn.

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# libpq for psycopg, plus build essentials for any wheels that need compiling.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements/ requirements/

# ---- dev --------------------------------------------------------------------
FROM base AS dev
RUN pip install -r requirements/dev.txt
COPY . .
ENV DJANGO_SETTINGS_MODULE=config.settings.dev
EXPOSE 8000
ENTRYPOINT ["bash", "docker-entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---- prod -------------------------------------------------------------------
FROM base AS prod
RUN pip install -r requirements/prod.txt
COPY . .
ENV DJANGO_SETTINGS_MODULE=config.settings.prod
RUN python manage.py collectstatic --noinput || true
EXPOSE 8000
ENTRYPOINT ["bash", "docker-entrypoint.sh"]
# `--workers 3` en sync = 3 requetes traitees SIMULTANEMENT, point. C'etait le
# plafond dur de la prod : au-dela, tout part en file d'attente puis en timeout.
#
# gthread + threads : Django est I/O-bound (il attend Postgres et Brevo), donc
# la concurrence utile = workers x threads, sans payer un process complet par
# unite de concurrence. 4 x 8 = 32 requetes simultanees (~x10) pour ~4 process.
#
# Les deux sont tunables par env pour s'adapter au VPS SANS rebuild d'image :
#   - workers : compter ~200-250 Mo de RSS par worker. Ne pas monter les
#     workers avant d'avoir verifie la RAM disponible.
#   - workers x threads doit rester < max_connections de Postgres (100 par
#     defaut), car CONN_MAX_AGE fait tenir une connexion par thread.
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --worker-class gthread --workers ${GUNICORN_WORKERS:-4} --threads ${GUNICORN_THREADS:-8} --timeout ${GUNICORN_TIMEOUT:-60}"]
