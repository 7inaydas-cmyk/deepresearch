---
status: accepted
date: 2026-09-16
---

# The session transport: a harness CLI's own login powers the model calls

The owner's deployments hold no API keys. Every real client authenticates one of two
ways: a harness login (Claude Code's OAuth file), or the harness itself — `claude -p`
print mode, `hermes -p glm -z` one-shot — whose own logged-in session pays for every
call. The provider seam's headline feature, key-env inference, was a door these
deployments never open.

## Decision

Each provider may declare a **harness** in `contract/providers.json` — a CLI whose
login powers model calls (`claude -p` for the claude provider; `hermes -p glm -z`,
resolved through `DR_GLM_HARNESS` where hermes lives in a container, for zai).
Transport resolution is **session-first**: if the harness command resolves on the
machine, `agent()` spawns it per call and deepresearch reads no credential at all;
key-env/OAuth HTTP is the fallback for headless servers; `DR_TRANSPORT=http` forces
the fallback explicitly.

Policy does not move (ADR-0001): the spawn is mechanism at the seam
(`run_harness()`); retries, the corrective re-ask, sentinel recovery and `shape()`
run over the harness's stdout exactly as over an HTTP response. A print mode has no
`tool_choice`, so the session prompt states the schema verbatim and demands bare
JSON; a tolerant extractor pulls the candidate object, and the seam — never the
extractor — decides validity. There is no max_tokens knob on a spawn, so an
unparseable reply always gets the corrective re-ask rather than budget growth.

Both transports were verified live before this ADR was accepted: `claude -p` and
`hermes -p glm -z` each answered a one-word probe, login-powered, no key in the path.

## Amendment (same day): the third transport, stdio

`DR_TRANSPORT=stdio` completes the matrix: **http | spawn-harness | stdio**. There is
no headless `zcode -p` (it is an Electron app), but running research *in the driving
window* does not need one — it needs the engine to hand its prompts to whatever
session is driving it. Over stdio the engine emits one JSON request per call
(`{id, prompt, schema}`) and reads one id-matched reply (`{id, reply}`); the driving
window IS the model, on its own subscription; zero spawns, zero credentials, zero
sockets. Calls serialize behind a lock — one window is one rater, and interleaved
replies could not be correlated by a human reading the stream. The same shaping,
sentinel and retry policy runs over every reply. Verified live by fifo before the
suite existed, then pinned hermetically (the first version of the test deadlocked the
engine when its harness thread died on a NameError — readline waits forever for a
rater that will never answer, which is the protocol's one genuine failure mode and
now a guarded test).

## Considered options

**An explicit `--transport session` opt-in** was rejected: it leaves HTTP as the
default posture, which is the opposite of the deployment reality this exists for.
Session-first with a forced-fallback flag matches it.

**Riding a harness's local proxy endpoint** (hermes exposes one) was rejected: it
reintroduces an endpoint and credential story per harness, and an OpenAI-wire adapter
would contradict ADR-0004's one-wire scope.

**A persistent harness process** (one spawn, many calls) is a measured future option:
~150 spawns per standard run each pay process start-up. Deferred until spawn cost is
measured as the bottleneck; correctness first.

## Consequences

- `preflight()` proves the harness answers with one spawned probe — same shape as the
  credential probe, same refusal text naming what actually failed.
- `describe()` says "session via claude -p — login-powered, no API key" and the run's
  `stats` carry `transport`.
- The byte-identity guarantee of ADR-0004 now reads *no-harness* byte-identity: on a
  machine with the CLI present, session wins even if a key is also set; the HTTP pins
  in the test suite force their transport explicitly.
- The ZCode skill and the Claude Code workflow remain session consumers at the
  protocol level — the Python CLI can now do the same thing natively, and a future
  simplification can point the skill at the CLI instead of re-implementing the
  orchestration in agent prose.
