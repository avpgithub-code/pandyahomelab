#!/bin/sh
# cricstat pull-based CD (F9). The NAS pulls images that CI published to GHCR; nothing pushes to the NAS.
# Run by DSM Task Scheduler as root (non-zero exit → DSM email), or by hand:
#   sh cd-pull.sh             deploy the newest published image of each service, if it changed
#   sh cd-pull.sh rollback    put back the image that was live before the last deploy
# Env: CRICSTAT_IMAGE_TAG (default: main), DOCKER (default: /usr/local/bin/docker).
#
# Each new image must pass a smoke test ON THE NAS (its CPU has no AVX; CI runners do) before it is
# tagged `<service>:latest`, the tag docker-compose.yml runs. The image it replaces is kept as
# `<service>:previous`. Batch services pick up `latest` on their next scheduled run; always-on
# services (cricstat-api, P0) will also be restarted and health-checked here.
set -eu

DOCKER=${DOCKER:-/usr/local/bin/docker}
REGISTRY=ghcr.io/avpgithub-code
TAG=${CRICSTAT_IMAGE_TAG:-main}
SERVICES="cricstat-pipeline"
LOG_DIR=/volume1/pandya-homelab/cricstat/logs
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/cd-$(date -u +%Y%m%d).log"

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$LOG"; }
short() { echo "$1" | sed 's/^sha256://' | cut -c1-12; }

smoke() {  # $1 = service, $2 = image; run as the operator UID like compose does
  case "$1" in
    cricstat-pipeline) "$DOCKER" run --rm -u 1026:100 "$2" --help >/dev/null 2>&1 ;;
    *) log "no smoke test defined for $1"; return 1 ;;
  esac
}

deploy() {
  svc=$1
  remote="$REGISTRY/$svc:$TAG"
  if ! "$DOCKER" pull -q "$remote" >/dev/null 2>&1; then
    log "FAIL $svc: cannot pull $remote"; return 1
  fi
  new=$("$DOCKER" image inspect -f '{{.Id}}' "$remote")
  old=$("$DOCKER" image inspect -f '{{.Id}}' "$svc:latest" 2>/dev/null || echo none)
  if [ "$new" = "$old" ]; then
    log "ok $svc up to date ($(short "$new"))"; return 0
  fi
  if ! smoke "$svc" "$remote"; then
    log "FAIL $svc: smoke test failed for $remote ($(short "$new")); kept $(short "$old")"; return 1
  fi
  [ "$old" != none ] && "$DOCKER" tag "$svc:latest" "$svc:previous"
  "$DOCKER" tag "$remote" "$svc:latest"
  log "deployed $svc $(short "$new") from $remote (previous $(short "$old"))"
}

rollback() {
  svc=$1
  if ! "$DOCKER" image inspect "$svc:previous" >/dev/null 2>&1; then
    log "FAIL $svc: no previous image to roll back to"; return 1
  fi
  "$DOCKER" tag "$svc:previous" "$svc:latest"
  log "rolled back $svc to $(short "$("$DOCKER" image inspect -f '{{.Id}}' "$svc:latest")")"
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
