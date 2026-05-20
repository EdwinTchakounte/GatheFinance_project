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
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
