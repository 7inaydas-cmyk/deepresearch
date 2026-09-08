---
status: accepted
date: 2026-09-08
---

# Prompt caching is refused: the only prompt big enough to cache cannot be reordered

No prompt block in this engine is marked with `cache_control`. The audit prompt keeps the
statement above the page text, and that order is load-bearing rather than incidental.

## What was proposed

An external review found `cache_read_input_tokens: 0` on every call and reported it as the
single biggest optimisation available: mark the system block and the static verify-lens
boilerplate as cacheable, for "conservatively 30–40% off total input tokens", described as
a one-line change with zero quality cost.

## Why the headline version is not available at all

Anthropic's prompt cache has a documented minimum cacheable prefix of ~1024 tokens. Measured
in this build:

| block | tokens | cacheable |
|---|---|---|
| system block | 47 | no |
| a whole verify prompt | 332–373 | no |
| the audit's page text | ~3000 | yes |

The system block is 47 tokens, not a large shared prefix. Marking it caches nothing and adds
a 25% cache-write surcharge against zero reads. The verify lenses are ~60% static boilerplate,
which is true and irrelevant: 60% of 350 tokens is still five times under the floor. The
review's stated fraction was right and its conclusion did not follow from it.

The audit prompt is the one prompt in the pipeline over the floor, and it is also the one
that repeats — 18 of 30 audit calls in each of two recorded 30-claim runs cite a page the run
already holds.

## Why the audit is not cached either

A cache covers a *prefix*. The page text sits after the statement, so caching it requires
moving the page above the claim. That was built, and then measured before shipping: the same
30 `(claim, url, page)` triples from `runs/v3-nudge-contract.json` were replayed through the
old prompt twice (a control for the judge's own noise) and through the reordered prompt.

| comparison | verdicts that differ | n |
|---|---|---|
| old vs old (control) | **0.000** | 30 |
| old vs reordered | **0.200** | 30 |

The judge disagreed with itself on 0 of 30 and with the reordered prompt on 6 of 30. With a
zero noise floor, every one of those six is attributable to the move. They ran both ways
(3 `partial`→`supported`, 2 `supported`→`partial`, 1 `partial`→`unreachable`), and the net
shifted the headline citation accuracy from 77.8% to 84.6% — a seven-point gain produced by
relocating a paragraph. Evidence: `runs/ab-audit-prompt-order-2026-09-08.json`.

## Decision

Do not cache. Nothing weighed against a seven-point drift in the number this project leads
with, because the tokens do not bill: the credential is a flat subscription, and `rateLimited`
is 0 across every recorded run. The saving was real and worth nothing; the cost was real and
landed on the one measurement everything else rests on.

### The census immediately justified itself

On its first live run the `usageUnrecorded` census reported three fields:

    cache_creation.ephemeral_5m_input_tokens
    cache_creation.ephemeral_1h_input_tokens
    output_tokens_details.thinking_tokens

Only the third was named in the review. The API also reports cache creation as a *nested*
`cache_creation` object broken down by TTL, which neither the review nor this change
predicted. A hardcoded list of the three fields the review named would have shipped, looked
correct, and still been silently short by two. Censusing every unrecognised numeric field
is what caught them — the whole point of preferring a census to a list.

The two token-shaped findings underneath the proposal were real and were fixed separately:
usage accounting was silently incomplete (`_record_usage` now counts cache fields and censuses
any usage key this build does not name), and pages were re-fetched per claim (`web_fetch` now
caches per URL, which removes the network cost of the repetition without touching a prompt).

## What would reopen this

- Billing changes to per-token, or `rateLimited` stops reading 0.
- A reordered audit prompt is shown to agree with the current one at the control's noise floor
  on a larger replay — the n=30 above can only detect a shift of roughly this size.
- Anthropic supports a cache breakpoint that is not a strict prefix, or drops the ~1024 floor
  far enough that the verify lenses come into range.

## Consequences

`cache_control` appears nowhere in the engine, and a test asserts that. `p_fact` carries a
comment saying its section order must not be rearranged for token reasons. Future reviews
that find `cache_read_input_tokens: 0` should read this file rather than re-derive it — the
zero is a decision, not an oversight.
