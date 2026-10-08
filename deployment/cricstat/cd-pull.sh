#!/bin/sh
# cricstat pull-based CD (F9). The NAS pulls images that CI published to GHCR; nothing pushes to the NAS.
# Run by DSM Task Scheduler as root (non-zero exit → DSM email), or by hand:
#   sh cd-pull.sh             deploy the newest published image of each service, if it changed
#   sh cd-pull.sh rollback    put back the image that was live before the last deploy
# Env: CRICSTAT_IMAGE_TAG (default: main), CRICSTAT_SERVICES (default: all three), DOCKER (default: /usr/local/bin/docker; may include
#      arguments, e.g. DOCKER="sudo -n docker" to test as the operator instead of root).
#
# Each new image must pass a smoke test ON THE NAS (its CPU has no AVX; CI runners do) before it is
# tagged `<service>:latest`, the tag docker-compose.yml runs. The image it replaces is kept as
# `<service>:previous`. Batch services pick up `latest` on their next scheduled run. Always-on
# services (cricstat-api) are then restarted and health-checked; if the live check fails, the
# previous image is put back and restarted, and the run exits 1 (DSM email).
set -eu

DOCKER=${DOCKER:-/usr/local/bin/docker}
REGISTRY=ghcr.io/avpgithub-code
TAG=${CRICSTAT_IMAGE_TAG:-main}
# CRICSTAT_SERVICES deploys a subset in order, e.g. the pipeline first when a schema change must
# be built before the API that reads it can go live (P0.5).
SERVICES=${CRICSTAT_SERVICES:-"cricstat-pipeline cricstat-models cricstat-api"}
ALWAYS_ON="cricstat-api"
HERE=$(cd "$(dirname "$0")" && pwd)
COMPOSE="$DOCKER compose -f $HERE/docker-compose.yml"
DATA_DB=/volume1/pandya-homelab/cricstat/data/db
API_URL=http://127.0.0.1:8040/v1/health
LOG_DIR=/volume1/pandya-homelab/cricstat/logs
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/cd-$(date -u +%Y%m%d).log"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$LOG"; }
short() { echo "$1" | sed 's/^sha256://' | cut -c1-12; }

smoke() {  # $1 = service, $2 = image; run as the operator UID like compose does
  case "$1" in
    cricstat-pipeline) $DOCKER run --rm -u 1026:100 "$2" --help >/dev/null 2>&1 ;;
    cricstat-api) smoke_api "$2" ;;
    # Every data/config check against the real DB, read-only, no network (the champion comes from
    # the forecast.sqlite cache when MLflow is unreachable), no writes.
    cricstat-models) $DOCKER run --rm -u 1026:100 --read-only --tmpfs /tmp --network none \
        -e CRICSTAT_LOG_DIR=/tmp/logs -e CRICSTAT_MLFLOW_URI=http://127.0.0.1:9 \
        -v "$DATA_DB:/cricstat/data/db:ro" "$2" selftest --quiet >/dev/null 2>&1 ;;
    *) log "no smoke test defined for $1"; return 1 ;;
  esac
}

wait_healthy() {  # $1 = URL; healthy = HTTP 200 with a build_id, within ~60 s
  i=0
  while [ $i -lt 30 ]; do
    if curl -fsS --max-time 3 "$1" 2>/dev/null | grep -q '"build_id":[0-9]'; then return 0; fi
    i=$((i + 1)); sleep 2
  done
  return 1
}

smoke_api() {  # throwaway container on 127.0.0.1:8049 against the real DB (read-only)
  name=cricstat-api-smoke
  $DOCKER rm -f "$name" >/dev/null 2>&1 || true
  $DOCKER run -d --name "$name" -u 1026:100 --read-only --tmpfs /tmp \
    -v "$DATA_DB:/cricstat/data/db:ro" -v "$LOG_DIR:/cricstat/logs:ro" \
    -p 127.0.0.1:8049:8000 "$1" >/dev/null 2>&1 || return 1
  ok=0
  if wait_healthy http://127.0.0.1:8049/v1/health \
     && curl -fsS --max-time 10 http://127.0.0.1:8049/v1/status >/dev/null 2>&1; then ok=1; fi
  [ $ok -eq 1 ] || $DOCKER logs --tail 20 "$name" 2>&1 | sed 's/^/  smoke: /' | tee -a "$LOG"
  $DOCKER rm -f "$name" >/dev/null 2>&1 || true
  [ $ok -eq 1 ]
}

is_always_on() { case " $ALWAYS_ON " in *" $1 "*) return 0 ;; esac; return 1; }

restart() {  # recreate the container from <service>:latest and check it live
  $COMPOSE up -d --no-deps --force-recreate "$1" >/dev/null 2>&1 && wait_healthy "$API_URL"
}

deploy() {
  svc=$1
  remote="$REGISTRY/$svc:$TAG"
  if ! $DOCKER pull -q "$remote" >/dev/null 2>&1; then
    if ! $DOCKER image inspect "$svc:latest" >/dev/null 2>&1; then
      log "skip $svc: $remote not published yet (never deployed here)"; return 0
    fi
    log "FAIL $svc: cannot pull $remote"; return 1
  fi
  new=$($DOCKER image inspect -f '{{.Id}}' "$remote")
  # On a first deploy there is no :latest; inspect then fails (and may still print an empty line).
  old=$($DOCKER image inspect -f '{{.Id}}' "$svc:latest" 2>/dev/null) || old=none
  [ -n "$old" ] || old=none
  if [ "$new" = "$old" ]; then
    if is_always_on "$svc" && ! curl -fsS --max-time 3 "$API_URL" >/dev/null 2>&1; then
      if restart "$svc"; then log "ok $svc up to date ($(short "$new")); was down, restarted"
      else log "FAIL $svc: up to date but unhealthy after restart"; return 1; fi
      return 0
    fi
    log "ok $svc up to date ($(short "$new"))"; return 0
  fi
  if ! smoke "$svc" "$remote"; then
    log "FAIL $svc: smoke test failed for $remote ($(short "$new")); kept $(short "$old")"; return 1
  fi
  if [ "$old" != none ]; then $DOCKER tag "$svc:latest" "$svc:previous"; fi
  $DOCKER tag "$remote" "$svc:latest"
  if is_always_on "$svc" && ! restart "$svc"; then
    if [ "$old" != none ]; then
      $DOCKER tag "$svc:previous" "$svc:latest"
      if restart "$svc"; then state="restored $(short "$old")"; else state="RESTORE ALSO FAILED"; fi
    else
      state="no previous image"
    fi
    log "FAIL $svc: $(short "$new") unhealthy after restart; rolled back: $state"; return 1
  fi
  log "deployed $svc $(short "$new") from $remote (previous $(short "$old"))"
}

rollback() {
  svc=$1
  if ! $DOCKER image inspect "$svc:previous" >/dev/null 2>&1; then
    log "FAIL $svc: no previous image to roll back to"; return 1
  fi
  $DOCKER tag "$svc:previous" "$svc:latest"
  if is_always_on "$svc" && ! restart "$svc"; then
    log "FAIL $svc: unhealthy after rollback"; return 1
  fi
  log "rolled back $svc to $(short "$($DOCKER image inspect -f '{{.Id}}' "$svc:latest")")"
}

action=${1:-deploy}
failures=0
for svc in $SERVICES; do
  case "$action" in
    deploy) deploy "$svc" || failures=$((failures + 1)) ;;
    rollback) rollback "$svc" || failures=$((failures + 1)) ;;
    *) echo "usage: $0 [deploy|rollback]" >&2; exit 64 ;;
  esac
done
[ "$failures" -eq 0 ] || exit 1
