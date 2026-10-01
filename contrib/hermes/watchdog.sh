#!/usr/bin/env sh
# The no-LLM half of the hermes watchdog. Runs on a schedule (hermes cron,
# monitor-gated) and exits 0 when the deployment is healthy - meaning the cron
# stays asleep and spends no tokens. Any nonzero exit wakes the agent, whose
# prompt does the LLM work: run the sync, verify, report.
#
# Registering (once, inside the hermes-agent container; monitor-gated means the
# agent runs only when this script's OUTPUT changes, so a stable healthy line
# costs nothing):
#   docker exec hermes-agent /opt/hermes/.venv/bin/hermes -p glm cron create \
#     --name deepresearch-watchdog --deliver telegram \
#     --monitor-script deepresearch-watchdog.sh "0 9 * * *" \
#     "The deepresearch deployment watchdog changed - act on exactly what its
#      diff reports: skill drift -> sh /opt/data/deepresearch-repo/contrib/hermes/
#      sync-skill.sh, verify the trees it named, re-run the watchdog, report
#      old->new versions; sync failure -> ALERT with the error; searxng down ->
#      report that the gateway's general-web search is degraded."
# sync-skill.sh installs this script into every profile's scripts/ dir, which
# is where the glm cron resolves --monitor-script from.
#
# Two checks per tick, both chosen because they failed silently in production
# (2026-09-16):
#   1. skill drift  - hermes serves real files that only sync-skill.sh moves;
#      a drifted tree serves yesterday's instructions to messenger agents.
#   2. searxng      - the gateway's general-web search backend, probed from
#      THIS vantage, on CONTENT not status code: a suspended instance answers
#      HTTP 200 with zero results and every engine in unresponsive_engines
#      (measured 2026-09-16 under two concurrent runs). Rule: health-check on
#      result content, never on the status code. The instance is published to
#      127.0.0.1:8888 on the host and answers as searxng:8080 from the docker
#      network; probing the wrong one reports health while every in-container
#      search is dead.
#
# Vantage note: when hermes cron runs this inside the hermes-agent container,
# HERMES_HOME=/opt/data and the default probe URL below is the gateway's own
# view of searxng - which is the point. DR_REPO and DR_WATCHDOG_SEARXNG
# override both for testing from anywhere.
set -u

REPO="${DR_REPO:-}"
if [ -z "$REPO" ]; then
  for c in /opt/data/deepresearch-repo "$HOME/.local/share/hermes-agent/deepresearch-repo"; do
    if [ -f "$c/contrib/hermes/sync-skill.sh" ]; then REPO="$c"; break; fi
  done
fi
if [ -z "$REPO" ] || [ ! -f "$REPO/contrib/hermes/sync-skill.sh" ]; then
  echo "WATCHDOG FAIL: no deepresearch checkout found (set DR_REPO)"
  exit 1
fi

status=0

if ! out=$(sh "$REPO/contrib/hermes/sync-skill.sh" --check 2>&1); then
  echo "skill drift detected:"
  echo "$out"
  status=1
else
  echo "$out"
fi

url="${DR_WATCHDOG_SEARXNG:-http://searxng:8080/search?format=json&q=test}"
resp=$(curl -s -m 12 -w '\n%{http_code}' "$url" 2>/dev/null) || resp=""
code=$(printf '%s' "$resp" | tail -n 1)
body=$(printf '%s' "$resp" | sed '$d')
if [ "$code" != "200" ] || [ -z "$body" ]; then
  echo "searxng unreachable from this vantage: HTTP ${code:-000} for $url"
  status=1
else
  # Content check: count results and name the suspended engines. A 200 with an
  # empty result list is the suspended state the status code cannot see.
  read -r nres susp <<EOF
$(printf '%s' "$body" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print(-1, "unparseable")
else:
    eng = [e[0] for e in (d.get("unresponsive_engines") or []) if e]
    print(len(d.get("results") or []), ",".join(eng[:8]) or "-")
')
EOF
  # A missing python3 or a hard parse crash must read as broken, not healthy.
  [ -n "$nres" ] || nres=-1
  if [ "$nres" = "-1" ]; then
    echo "searxng answered HTTP 200 but the body is not JSON - instance broken, not busy"
    status=1
  elif [ "$nres" -lt 1 ]; then
    echo "searxng answers 200 but served 0 results (suspended engines: ${susp:-unknown}) for $url"
    status=1
  fi
fi

# 3. firecrawl - the rendered-read backend, probed on CONTENT like everything else:
# a real scrape must return markdown, never a status code. The stack sat fully DOWN
# for 13 days before 2026-10-01 with nothing watching it. The HOST-side keeper
# (contrib/firecrawl/firecrawl-keeper.sh, cron */5) revives and self-heals it;
# this check is the in-container vantage - the one the engine's sandboxes use -
# and the keeper's intervention log (default: $HERMES_HOME/firecrawl-keeper.log,
# written actions-only) is reported below so an intervention wakes this watchdog
# exactly once via the monitor gate.
fc="${DR_WATCHDOG_FIRECRAWL:-http://firecrawl:3002}"
fc_body=$(curl -s -m 45 -X POST "$fc/v1/scrape" -H 'Content-Type: application/json' \
            -d '{"url":"https://example.com","formats":["markdown"]}' 2>/dev/null) || fc_body=""
fc_ok=0
if [ -n "$fc_body" ]; then
  printf '%s' "$fc_body" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
md = ((d.get("data") or {}).get("markdown") or "")
sys.exit(0 if d.get("success") and md.strip() else 1)' 2>/dev/null && fc_ok=1
fi
if [ "$fc_ok" -ne 1 ]; then
  echo "firecrawl failed the content probe from this vantage ($fc): a real scrape returned no markdown"
  status=1
fi

# Keeper interventions: reported only when the keeper LOG moved in the last 25h
# (one daily tick plus slack), so a healthy stack adds no line and the monitor
# gate stays asleep. The line disappearing again later reads as "recovered".
klog="${DR_WATCHDOG_KEEPER_LOG:-${HERMES_HOME:-/opt/data}/firecrawl-keeper.log}"
if [ -f "$klog" ] && find "$klog" -mmin -1500 >/dev/null 2>&1 && [ -s "$klog" ]; then
  echo "firecrawl keeper acted in the last 24h (host cron revived/restarted something):"
  tail -n 10 "$klog" | sed 's/^/  /'
fi

# 4. disk - a full disk kills every tenant on this host at once. Reported only at
# >= 80% so a healthy day adds no line; the number itself is the alert, and a
# one-point change re-wakes only while the condition holds.
disk_pct=$(df -P / 2>/dev/null | awk 'NR==2 {gsub("%",""); print $5}')
case "$disk_pct" in
  ''|*[!0-9]*) ;;                       # unparseable df: say nothing, fail nothing
  *) if [ "$disk_pct" -ge 80 ]; then
       echo "disk at ${disk_pct}% - a full disk takes every container on this host down"
     fi ;;
esac

exit "$status"
