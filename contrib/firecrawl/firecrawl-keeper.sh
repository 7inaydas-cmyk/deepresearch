#!/usr/bin/env bash
# firecrawl-keeper: the CONTINUOUS half of firecrawl care (2026-10-01).
#
# The stack sat fully DOWN for 13 days - every compose service shipped restart:"no",
# so one playwright crash (exit 1, mid-scrape) or one host reboot and nothing came
# back, while deepresearch runs silently degraded to the stdlib ladder. Two layers
# now keep it up:
#   1. docker-compose.override.yml sets restart: unless-stopped on every long-running
#      service (docker itself revives a crashed container, and brings the stack back
#      after a daemon/host restart unless it was explicitly stopped).
#   2. THIS script, from a host cron every 5 minutes: `docker compose up -d` is
#      idempotent and covers everything the restart policy cannot (an image pull,
#      a compose edit, a `docker compose down` someone ran); unhealthy containers
#      are restarted individually; and a CONTENT probe - a real scrape must return
#      markdown, never a status code - restarts api+playwright when it fails.
#
# The log records ACTIONS ONLY (a healthy tick writes nothing), so the daily
# deepresearch watchdog (contrib/hermes/watchdog.sh, monitor-gated, telegram) can
# append this log's recent tail and wake the owner exactly when the keeper acted.
# The default log path lives under the hermes home BECAUSE that is the one
# directory the in-container watchdog can read (/opt/data from its vantage).
#
# Registering (once, on the host):
#   crontab -e
#     */5 * * * * /path/to/deepresearch/contrib/firecrawl/firecrawl-keeper.sh
set -u    # NOT -e: a failing check must fall through to the next; the keeper's job
          # is to act on what is still checkable, not to abort on what is not

COMPOSE_DIR="${FC_COMPOSE_DIR:-$HOME/Desktop/firecrawl}"
LOG="${FC_KEEPER_LOG:-$HOME/.local/share/hermes-agent/firecrawl-keeper.log}"
PROBE_URL="${FC_PROBE_URL:-http://127.0.0.1:3002}"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; }

# Rotate at 1MB - the tail the watchdog reports should be recent interventions,
# not months of them.
if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt 1000000 ]; then
  tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
  log "KEEPER: log rotated at 1MB"
fi

# 1. Revive: idempotent. `up -d` starts anything down and leaves running services
#    alone; --remove-orphans keeps stale service containers from lingering after a
#    compose edit. Its stdout is captured and logged ONLY when it actually STARTED
#    or CREATED something - a healthy no-op tick prints "Running" lines that must
#    not reach the log, or the monitor-gated daily watchdog would wake every day.
#    A dead docker daemon is the one failure here we cannot fix - it is logged, and
#    the daily watchdog's own firecrawl probe reports it.
_up_out="$(mktemp)"
if ! (cd "$COMPOSE_DIR" && docker compose up -d --remove-orphans > "$_up_out" 2>&1); then
  log "KEEPER: docker compose up failed - is the docker daemon down?"
  cat "$_up_out" >> "$LOG"; rm -f "$_up_out"; exit 0
fi
# Only container ACTION lines, and NOT foundationdb-init: that one-shot re-runs on
# every `up -d` by design (it initializes then exits), so its "Started" line would
# log - and wake the daily telegram - on every healthy tick. The compose
# variable-warning noise is dropped for the same reason: signal, not chatter.
_restarted="$(grep -E '^ *Container ' "$_up_out" 2>/dev/null \
              | grep -vE 'foundationdb-init' \
              | grep -E 'Started|Recreated' || true)"
if [ -n "$_restarted" ]; then
  log "KEEPER: compose brought something up:"
  printf '%s\n' "$_restarted" | sed 's/^/    /' >> "$LOG"
fi
rm -f "$_up_out"

# 2. Up-but-unhealthy: rabbitmq and nuq-postgres carry real healthchecks; restart
#    whatever docker itself has marked unhealthy. (api/playwright/redis/foundationdb
#    declare none - for them the content probe below IS the healthcheck.)
for c in $(docker ps --filter name=firecrawl- --filter health=unhealthy -q 2>/dev/null); do
  name="$(docker inspect "$c" --format '{{.Name}}' 2>/dev/null || echo "$c")"
  if docker restart "$c" >> "$LOG" 2>&1; then
    log "KEEPER: restarted unhealthy $name"
  fi
done

# 3. Content probe: POST /v1/scrape for example.com and demand non-empty markdown -
#    the same rule the engine's adoption probe and the daily watchdog use. A 200
#    with success:false or an empty shell is a FAILURE here. On failure, restart
#    the two services that serve scrapes; a transient blip costs one restart, a
#    real breakage gets restarted every 5 minutes AND lands in the watchdog report.
probe_ok=0
body="$(timeout 45 curl -s -X POST "$PROBE_URL/v1/scrape" \
        -H 'Content-Type: application/json' \
        -d '{"url":"https://example.com","formats":["markdown"]}' 2>/dev/null || true)"
if [ -n "$body" ]; then
  printf '%s' "$body" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
md = ((d.get("data") or {}).get("markdown") or "")
sys.exit(0 if d.get("success") and md.strip() else 1)' 2>/dev/null && probe_ok=1
fi

if [ "$probe_ok" -ne 1 ]; then
  log "KEEPER: content probe failed (no markdown from a real scrape) - restarting api + playwright-service"
  (cd "$COMPOSE_DIR" && docker compose restart api playwright-service >> "$LOG" 2>&1)
fi

exit 0
