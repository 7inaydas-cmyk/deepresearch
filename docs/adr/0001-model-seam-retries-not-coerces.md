---
status: accepted
date: 2026-09-07
---

# The model seam retries rather than coerces, and callers do not re-validate

Every model response enters the engine through `agent()`, which shapes it to the schema
that requested it (`shape()`): declared arrays become lists, array items missing a required
key are dropped and logged, enums and booleans are checked. A response that is still wrong
at the top level after that — a `support` outside its enum, a `refuted` that is not a
boolean — is re-asked with a correction naming the field, and after the retries `agent()`
returns `None`. It never maps `"false"` to `False` or `"Supported"` to `"supported"`, and
callers never re-validate what the seam hands them.

## Considered options

**A repair table** ("true"/"false"/"yes"/"no" → bool, case-folded enums) would save a model
call on a rare path. Rejected because the boolean in question decides whether a claim is
killed, and the line between "obvious repair" and "guess" drifts; the project's recorded
faults are precisely values that were quietly made to look right.

**Keeping caller guards as defence in depth** was rejected because two validation layers
with no statement of which is authoritative is the ambiguity that produced nine different
guard dialects across twelve call sites in the first place.

## Consequences

A caller writes `if not x: return` and nothing else. A malformed response costs one extra
model call and then yields `unverified` rather than a verdict — the honest outcome. The
retry loop inside `agent()` is not exercised by the test suite, which stubs `agent()`; the
pure `shape()` is tested directly per schema, and the stub routes its fixtures through it.
