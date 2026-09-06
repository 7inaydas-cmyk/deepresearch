#!/usr/bin/env sh
# Prove the instance is actually serving JSON before a research run depends on it.
# A SearXNG that answers on / but 403s on format=json is the common failure, and it
# looks exactly like "the web has nothing on this" once it reaches the pipeline.
set -eu
URL="${DR_SEARXNG_URL:-http://127.0.0.1:8888}"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -m 20 "$URL/search?format=json&q=test")
if [ "$CODE" != "200" ]; then
  echo "FAIL: $URL/search?format=json returned HTTP $CODE"
  echo "      Most likely 'formats: [html, json]' is missing from settings.yml."
  exit 1
fi
N=$(curl -s -m 20 "$URL/search?format=json&q=open+source+deep+research" \
    | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("results") or []))')
echo "OK: $URL serves JSON and returned $N results for a live query."
[ "$N" -gt 0 ] || { echo "FAIL: 200 but zero results — the upstream engines are being blocked too."; exit 1; }
