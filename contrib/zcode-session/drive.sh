#!/usr/bin/env bash
# Drive deepresearch over the stdio transport from an agent window (ADR-0005).
#
#   dr-launch <question> [depth]     -> prints paths; the engine then WAITS for answers
#   dr-next                          -> prints the pending request (or "waiting")
#   dr-answer '<json reply>'         -> answers the pending request by id
#
# Failure modes, stated: if you stop answering, the engine blocks until its socket
# timeout (the one real hang class - a rater that never answers); an unterminated
# partial line on the fifo has the same effect. A malformed or mismatched-id reply
# is refused and retried with a new id - tail -1 always sees the newest request.
# DR_DEPTHS_FILE may point at a custom depth contract (e.g. a minimal e2e fixture);
# every depth must keep perspectives >= 3 or the plan schema will reject the reply.
#
# The engine emits one JSON request per call ({id, prompt, schema}) on its stdout and
# blocks until a matching-id reply arrives on the answer fifo. The WINDOW is the model:
# read the request, answer it as the subagent prompt asks, echo the reply. One request
# at a time - the transport serializes by design (one window is one rater).
set -euo pipefail
RUN="${DR_RUN_DIR:-/tmp/dr-stdio}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

case "${1:-}" in
  dr-launch)
    Q="${2:?question required}"; DEPTH="${3:-standard}"
    # An unset DR_SEARXNG_URL silently drops the searxng backend from the chain, and
    # once DDG/Mojeek are blocked the run degrades to Wikipedia/Crossref filler -
    # which reads as "the web has nothing on this". Measured 2026-09-16: a session
    # concluded Mode A was doomed when a local instance was alive the whole time at
    # the host publish. Adopt one only when it actually ANSWERS (content, not status
    # code); an explicit DR_SEARXNG_URL always wins and is never second-guessed.
    if [ -z "${DR_SEARXNG_URL:-}" ]; then
      for c in http://127.0.0.1:8888 http://127.0.0.1:8080; do
        if (cd "$REPO" && DR_SEARXNG_URL= python3 -c "
import sys; sys.path.insert(0, '.')
from deepresearch.search import probe_searxng
sys.exit(0 if (probe_searxng(sys.argv[1]) or 0) > 0 else 1)" "$c" 2>/dev/null); then
          DR_SEARXNG_URL="$c"
          echo "searxng: adopting $c (probed live: answers with results)"
          break
        fi
      done
    fi
    mkdir -p "$RUN"; rm -f "$RUN/req.out" "$RUN/ans.fifo" "$RUN/run.log" "$RUN/report.json"
    mkfifo "$RUN/ans.fifo"
    # A held-open writer keeps the engine's stdin alive between answers; without it
    # the fifo EOFs after the first reply and every later call reads nothing.
    sleep 7200 > "$RUN/ans.fifo" &
    echo $! > "$RUN/keeper.pid"
    # NOT the engine's own --bg: that re-exec redirects the child's stdout to a log,
    # and stdout IS the request stream. The subshell's & detaches enough for a window.
    ( cd "$REPO" && DR_PROVIDER="${DR_PROVIDER:-glm}" DR_TRANSPORT=stdio \
        DR_SEARXNG_URL="${DR_SEARXNG_URL:-}" \
        python3 -m deepresearch --question "$Q" --depth "$DEPTH" \
        --out "$RUN/report.json" \
        < "$RUN/ans.fifo" > "$RUN/req.out" 2> "$RUN/run.log" ) &
    echo "launched: requests=$RUN/req.out log=$RUN/run.log report=$RUN/report.json"
    ;;
  dr-next)
    tail -1 "$RUN/req.out" 2>/dev/null || echo "waiting"
    ;;
  dr-answer)
    REPLY="${2:?reply json required}"
    REQ="$(tail -1 "$RUN/req.out")"
    ID="$(printf '%s' "$REQ" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
    # ONE line: the engine reads a single readline per request. A pretty-printed
    # multi-line reply would arrive as a broken first line and fail the exchange -
    # compact the reply through python instead of trusting the caller's formatting.
    printf '%s' "$REPLY" | python3 -c "
import json, sys
reply = json.load(sys.stdin)
print(json.dumps({'id': int(sys.argv[1]), 'reply': reply}, separators=(',', ':')))
" "$ID" > "$RUN/ans.fifo"
    echo "answered id $ID"
    ;;
  *) echo "usage: dr-launch <question> [depth] | dr-next | dr-answer '<json>'" >&2; exit 2 ;;
esac
