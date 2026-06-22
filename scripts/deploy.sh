#!/usr/bin/env bash
# Tab — Deploy auf Hetzner.
#
#   ./scripts/deploy.sh                 # git pull + build + up -d + Healthcheck
#   ./scripts/deploy.sh --no-cache      # ohne Layer-Cache bauen
#   ./scripts/deploy.sh --skip-pull     # ohne git pull
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.prod.yml"

SKIP_PULL=0
BUILD_FLAGS=""
for arg in "$@"; do
  case "$arg" in
    --skip-pull) SKIP_PULL=1 ;;
    --no-cache)  BUILD_FLAGS="--no-cache" ;;
    *) echo "Unbekanntes Argument: $arg"; exit 1 ;;
  esac
done

# Sanity
[ -f docker-compose.prod.yml ] || { echo "docker-compose.prod.yml fehlt"; exit 1; }
[ -f .env ] || { echo "FEHLER: .env fehlt. Aus .env.example erstellen."; exit 1; }
mkdir -p /opt/appdata/tab/data

if [ "$SKIP_PULL" -eq 0 ] && [ -d .git ]; then
  echo "==> git pull"
  git fetch --all --prune
  git pull --ff-only
fi

echo "==> build"
# shellcheck disable=SC2086
$COMPOSE build $BUILD_FLAGS

echo "==> up -d (immer ohne Service-Filter, damit depends_on/health greift)"
$COMPOSE up -d

echo "==> warte auf Backend-Health"
for i in $(seq 1 30); do
  status=$(docker inspect -f '{{.State.Health.Status}}' tab-backend 2>/dev/null || echo "starting")
  if [ "$status" = "healthy" ]; then echo "Backend healthy."; break; fi
  sleep 3
  [ "$i" -eq 30 ] && { echo "FEHLER: Backend nicht healthy."; docker logs --tail 40 tab-backend; exit 1; }
done

echo "==> Status"
$COMPOSE ps
echo
echo "Fertig. Logs:  docker logs -f tab-backend   |   docker logs -f tab-frontend"
