#!/usr/bin/env bash
# =============================================================================
# inspect-dmz.sh — RELEVÉ (lecture seule) de la DMZ cliente avant bootstrap Gathé
# =============================================================================
# À lancer SUR le serveur cliente (169.58.69.78) en root (ou user du groupe docker).
# Ne modifie RIEN. Sort un rapport à copier/coller pour remplir infra/.env.prod.
#
#   bash inspect-dmz.sh
#
# Objectif : récupérer les 4 inconnues du rattachement DMZ ->
#   1) EDGE_NETWORK        (réseau du Traefik v3.3, ingress + TLS)
#   2) DATA_NETWORK        (réseau des bases Postgres/MinIO)
#   3) alias/host Postgres (pour DATABASE_URL) + version
#   4) TRAEFIK_CERTRESOLVER (nom exact du resolver ACME dans LEUR Traefik)
# + vérifier le provider Docker de Traefik (exposedByDefault / constraints),
#   sans quoi nos conteneurs pourraient être ignorés (ni route, ni cert).
# =============================================================================
set -uo pipefail

line() { printf '%s\n' "----------------------------------------------------------------------"; }
hdr()  { echo; line; echo "### $1"; line; }

hdr "0. Contexte hôte"
echo "hostname : $(hostname)"
echo "docker   : $(docker --version 2>/dev/null || echo 'ABSENT')"
echo "compose  : $(docker compose version --short 2>/dev/null || echo 'ABSENT')  (besoin >= 2.24 pour !reset)"

hdr "1. Réseaux Docker (repérer EDGE_NETWORK et DATA_NETWORK)"
echo "# EDGE_NETWORK = celui auquel Traefik est attaché (ingress)."
echo "# DATA_NETWORK = celui des bases (souvent 'internal: true')."
docker network ls
echo
echo "# Détail (driver / internal / conteneurs rattachés) :"
for net in $(docker network ls --format '{{.Name}}' | grep -viE '^(bridge|host|none)$'); do
  internal=$(docker network inspect "$net" -f '{{.Internal}}' 2>/dev/null)
  members=$(docker network inspect "$net" -f '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null)
  printf '  %-24s internal=%-5s  ::  %s\n' "$net" "$internal" "$members"
done

hdr "2. Conteneur Traefik (certresolver + provider Docker)"
TRAEFIK=$(docker ps --format '{{.Names}}' | grep -iE 'traefik' | head -1)
if [ -z "$TRAEFIK" ]; then
  echo "!! Aucun conteneur Traefik en cours d'exécution (grep 'traefik' vide)."
else
  echo "conteneur Traefik : $TRAEFIK"
  echo "réseaux de Traefik (=> EDGE_NETWORK est l'un d'eux) :"
  docker inspect "$TRAEFIK" -f '{{range $k,$v := .NetworkSettings.Networks}}  - {{$k}}{{"\n"}}{{end}}'
  echo "# --- Command / args statiques (certresolver ACME, exposedByDefault, constraints) ---"
  docker inspect "$TRAEFIK" -f '{{range .Config.Cmd}}{{println .}}{{end}}' 2>/dev/null \
    | grep -iE 'certificatesresolvers|acme|exposedbydefault|constraints|providers.docker' || echo "  (rien dans Cmd — voir fichier de conf statique ci-dessous)"
  echo "# --- Fichier de conf statique monté (traefik.yml / traefik.toml) ---"
  docker inspect "$TRAEFIK" -f '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' 2>/dev/null
  for f in /srv/edge/traefik.yml /srv/edge/traefik.toml /srv/edge/config/traefik.yml /etc/traefik/traefik.yml; do
    if [ -f "$f" ]; then
      echo "  >>> $f :"
      grep -inE 'certificatesresolvers|acme|email|exposedbydefault|constraints|entrypoints|websecure' "$f" | sed 's/^/     /'
    fi
  done
  echo "# --- Labels Traefik déjà posés sur les services existants (modèle à imiter) ---"
  docker ps --format '{{.Names}}' | while read -r c; do
    lbl=$(docker inspect "$c" -f '{{range $k,$v := .Config.Labels}}{{if (hasPrefix $k "traefik.")}}{{$k}}={{$v}} {{end}}{{end}}' 2>/dev/null)
    [ -n "$lbl" ] && printf '  [%s] %s\n' "$c" "$lbl"
  done
fi

hdr "3. Postgres (host/alias pour DATABASE_URL + version)"
PG=$(docker ps --format '{{.Names}}' | grep -iE 'postgres|pg' | head -1)
if [ -z "$PG" ]; then
  echo "!! Aucun conteneur Postgres repéré."
else
  echo "conteneur Postgres : $PG"
  echo "réseaux + alias (=> host à mettre dans DATABASE_URL) :"
  docker inspect "$PG" -f '{{range $k,$v := .NetworkSettings.Networks}}  - réseau {{$k}} | alias: {{range $v.Aliases}}{{.}} {{end}}{{"\n"}}{{end}}'
  echo "version serveur :"
  docker exec "$PG" postgres --version 2>/dev/null || echo "  (postgres --version indispo)"
  echo "bases existantes (vérifie si 'gathe_prod' existe déjà) :"
  docker exec "$PG" sh -lc 'psql -U "${POSTGRES_USER:-postgres}" -lqt 2>/dev/null | cut -d"|" -f1' 2>/dev/null | sed 's/^/  /' || echo "  (list DB indispo — auth ?)"
fi

hdr "4. MinIO (endpoint + bucket)"
MINIO=$(docker ps --format '{{.Names}}' | grep -iE 'minio' | head -1)
if [ -z "$MINIO" ]; then
  echo "!! Aucun conteneur MinIO repéré."
else
  echo "conteneur MinIO : $MINIO"
  echo "réseaux + alias (=> AWS_S3_ENDPOINT_URL interne = http://<alias>:9000) :"
  docker inspect "$MINIO" -f '{{range $k,$v := .NetworkSettings.Networks}}  - réseau {{$k}} | alias: {{range $v.Aliases}}{{.}} {{end}}{{"\n"}}{{end}}'
  echo "ports publiés :"
  docker inspect "$MINIO" -f '{{range $p,$b := .NetworkSettings.Ports}}  {{$p}} -> {{range $b}}{{.HostIp}}:{{.HostPort}} {{end}}{{"\n"}}{{end}}' 2>/dev/null
fi

hdr "5. RÉSUMÉ À REPORTER (colle ces 4 valeurs)"
cat <<'EOF'
  EDGE_NETWORK          = ................   (§1/§2 : réseau de Traefik)
  DATA_NETWORK          = ................   (§1/§3 : réseau de Postgres/MinIO)
  DATABASE host/alias   = ................   (§3 : alias Postgres joignable via DATA_NETWORK)
  TRAEFIK_CERTRESOLVER  = ................   (§2 : nom du resolver ACME, ex. letsencrypt)
  Postgres version      = ................   (§3)
  MinIO endpoint interne= http://.....:9000  (§4 : alias MinIO)
  Provider Docker Traefik: exposedByDefault=?  constraints=?  (§2 -> impacte nos labels)
EOF
line
echo "Relevé terminé — AUCUNE modification effectuée."
