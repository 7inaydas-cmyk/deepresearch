#!/usr/bin/env sh
# The no-LLM half of the hermes watchdog. Runs on a schedule (hermes cron,
# monitor-gated) and exits 0 when the deployment is healthy - meaning the cron
# stays asleep and spends no tokens. Any nonzero exit wakes the agent, whose
# prompt does the LLM work: run the sync, verify, report.
#
# Two checks per tick, both chosen because they failed silently in production
# (2026-09-16):
#   1. skill drift  - hermes serves real files that only sync-skill.sh moves;
#      a drifted tree serves yesterday's instructions to messenger agents.
#   2. searxng      - the gateway's general-web search backend, probed from
#      THIS vantage. The instance is published to 127.0.0.1:8888 on the host
#      and answers as searxng:8080 from the docker network; probing the wrong
#      one reports health while every in-container search is dead.
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
code=$(curl -s -m 12 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null) || code=000
if [ "$code" != "200" ]; then
  echo "searxng unreachable from this vantage: HTTP $code for $url"
  status=1
fi

exit "$status"
