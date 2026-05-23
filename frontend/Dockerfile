# syntax=docker/dockerfile:1
# ---- Frontend: Next.js site vitrine (npm workspaces) ------------------------
# `dev` target = next dev (use with bind mounts); `runner` target = next start.

FROM node:22-slim AS base
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# ---- deps: install once, cached on the workspace manifests ------------------
FROM base AS deps
COPY package.json package-lock.json* ./
COPY apps/site/package.json apps/site/package.json
COPY apps/admin/package.json apps/admin/package.json
COPY apps/portal/package.json apps/portal/package.json
COPY packages/config/package.json packages/config/package.json
COPY packages/ui/package.json packages/ui/package.json
RUN npm install --no-audit --no-fund

# ---- dev --------------------------------------------------------------------
FROM base AS dev
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--workspace", "@gathe/site", "--", "-H", "0.0.0.0", "-p", "3000"]

# ---- builders ---------------------------------------------------------------
# Un builder par workspace pour pouvoir publier des images distinctes en prod.
# Les ARGs reçoivent les URLs cibles au build (Next inline les NEXT_PUBLIC_*).
FROM base AS builder-site
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG CMS_API_URL=http://backend:8000
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ARG NEXT_PUBLIC_PORTAL_URL=http://localhost:3201
ENV CMS_API_URL=$CMS_API_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_PORTAL_URL=$NEXT_PUBLIC_PORTAL_URL
RUN npm run build --workspace @gathe/site

FROM base AS builder-portal
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG BACKEND_INTERNAL_URL=http://backend:8000
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ENV BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
RUN npm run build --workspace @gathe/portal

FROM base AS builder-admin
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG BACKEND_INTERNAL_URL=http://backend:8000
ARG NEXT_PUBLIC_PORTAL_URL=http://localhost:3201
ENV BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL \
    NEXT_PUBLIC_PORTAL_URL=$NEXT_PUBLIC_PORTAL_URL
RUN npm run build --workspace @gathe/admin

# ---- runners (production) ---------------------------------------------------
# Anciens nom `runner` conservé comme alias du site pour ne rien casser.
FROM base AS runner
ENV NODE_ENV=production
COPY --from=builder-site /app ./
EXPOSE 3000
CMD ["npm", "run", "start", "--workspace", "@gathe/site", "--", "-H", "0.0.0.0", "-p", "3000"]

FROM base AS runner-site
ENV NODE_ENV=production
COPY --from=builder-site /app ./
EXPOSE 3000
CMD ["npm", "run", "start", "--workspace", "@gathe/site", "--", "-H", "0.0.0.0", "-p", "3000"]

FROM base AS runner-portal
ENV NODE_ENV=production
COPY --from=builder-portal /app ./
EXPOSE 3000
CMD ["npm", "run", "start", "--workspace", "@gathe/portal", "--", "-H", "0.0.0.0", "-p", "3000"]

FROM base AS runner-admin
ENV NODE_ENV=production
COPY --from=builder-admin /app ./
EXPOSE 3000
CMD ["npm", "run", "start", "--workspace", "@gathe/admin", "--", "-H", "0.0.0.0", "-p", "3000"]
