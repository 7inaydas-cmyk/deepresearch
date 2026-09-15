---
status: accepted
date: 2026-09-15
---

# One wire, many providers: transport facts live in a contract, policy stays in agent()

Until 2026-09-15 the Python CLI was built on exactly one provider. Seven module
constants wired Anthropic into `engine.py` — the key env, the Claude Code OAuth
login file, the claude-cli user-agent and beta headers, the "You are Claude Code"
identity block, the endpoint, the default model — and `agent()` assembled the
transport itself. Adding GLM 5.3 (Z.ai, Anthropic-compatible endpoint, plain API
key) meant either duplicating that head per provider or giving the facts one home.

The seam is `deepresearch/providers.py` behind
`contract/providers.json`: `select()` resolves which provider (env, then
one-set-key inference, then the contract default), `transport()` returns the
assembled facts (URL, headers, credential, identity block, default model), and
`describe()` names them for `--selftest` and preflight. `agent()`'s request head
collapses to one call; everything after it — retries, the corrective re-ask,
`<UNKNOWN>` sentinel recovery, max_tokens growth, the 429 backoff — is
provider-agnostic policy and stays where ADR-0001 put it.

## Considered options

**A `Provider` interface with per-provider subclasses** (a `complete(body)` method,
retry policy inside each adapter) was rejected: it moves policy that is identical
across both providers into two places, and the retry loop is interlocked with the
corrective re-ask and the max_tokens growth — splitting it per provider would
duplicate the most defect-prone code in the file.

**A rich registry** (per-provider rate-limit curves, model aliases, arbitrary
header-from-env maps) was rejected as speculative generality: only one backoff
curve has ever been measured (the Claude subscription one), and putting an
unmeasured GLM curve into contract data would be the "asserted, not measured"
failure this repo's whole history is written against. The registry carries only
facts that exist today.

**Inference from which key variable is set** (no `DR_PROVIDER` needed for the
common case) was accepted WITH a loud ambiguity refusal: exactly one set key
selects that provider; two set keys are refused naming both, because resolving by
dict order would bill a different account than the user asked for. Explicit
`DR_PROVIDER` beats inference; an unknown value is refused listing valid names.

## Consequences

- With `DR_PROVIDER` unset and no GLM key set, the Anthropic path is byte-identical
  to before — same URL, same headers per scheme, same identity block, same default
  model — because the prompts were calibrated against that configuration and an
  unused option must not perturb it. This is pinned by test.
- A GLM run is honest on the wire: no claude-cli user-agent, no OAuth beta headers,
  and an identity block that says GLM rather than claiming to be Claude Code. Every
  `AuthError` names the SELECTED provider's key env — a GLM run is never told to set
  `ANTHROPIC_API_KEY`.
- `ZAI_API_KEY` (alias `GLM_API_KEY`) is the one-env-var path: set it and run. The
  glm endpoint (`https://api.z.ai/api/anthropic`, overridable via `GLM_BASE_URL`) is
  the vendor's documented Anthropic-compatible endpoint; nothing in this repo can
  verify an endpoint from a JSON file, so `preflight()` and `--selftest` are the
  live proof, run on the first call of every run.
- A provider that does not speak the Anthropic Messages wire format needs a real
  adapter and its own ADR; the contract's `$comment` says so, and nothing here
  pretends otherwise.
- The JS build is unaffected by design: its runtime owns the model, so it has no
  provider to choose — recorded in `tests/test_parity.py` under PYTHON_ONLY.
