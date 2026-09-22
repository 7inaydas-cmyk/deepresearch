# Contributing

## The one rule

Every test in `tests/test_pipeline.py` exists because something actually broke, and the
comment above it says what. If you fix a bug, add the test that would have caught it, and
write down what the failure looked like. A test with no story attached is a test nobody
will dare delete in two years.

## Running the tests

```bash
python3 tests/test_pipeline.py        # the engine: no API key, no network, a few seconds
python3 tests/test_conformance.py     # every gate proves a good and a bad reference
node tests/claude-code/conformance.mjs   # the JS build answers the SAME file
cd tests/claude-code && node test-workflow.mjs   # the JS build end to end, model stubbed
python3 tests/test_parity.py          # neither build is missing a feature the other has
```

The suite stubs the model and the network, so you can change the pipeline and see the
consequences without spending a token. If your change needs a live call to be tested, it is
probably in the wrong place — push the judgement into a pure function and test that.

## Adding or changing a gate

A gate accepts or rejects — a quote location, a schema leaf, a prose check, the
ambiguity guard. It must carry both references in `contract/conformance.json`: a `good`
one it accepts and a `bad` one it catches. The structural rule is enforced, and the half
that bites is the second one: a gate whose bad references answer exactly what its good
ones answer has never been observed to reject anything, however many cases it has.

That rule runs at **preflight, before any API call**, not only in CI. A build whose gates
are broken exits `CONTRACT` (4) and spends no tokens, because a report produced by broken
checks is worse than no report.

Write the bad reference before the fix, and let it teach you what the gate is for. The
first bad reference written for `is_prose` was a navigation wordlist — which is readable
text and correctly passed. The gate detects binary wearing a text costume, not
boilerplate, and writing the reference is what surfaced that.

Do not delete a reference to make this green.

## Archiving a run in `runs/`

Copy the report in, then **regenerate the README's issue-#9 table**:

```bash
cp /tmp/my-run.json runs/v13-something.json
python3 tools/compare_regimes.py --dropped-md   # paste the block into README.md
python3 tests/test_pipeline.py                  # the guard compares the two
```

A test asserts the README block is byte-identical to what the tool emits from `runs/`, so
archiving a run that carries a `droppedSample` and not regenerating turns the suite red.
That coupling is the point — the table drifted once by five samples to eight, and its
headline said "four of five" where no stated rule gave four — but it was undocumented
until a review called the guard "vestigial". It is load-bearing; this is how you satisfy it.

The conclusion sentence is derived from the tally, so a new sample can legitimately change
it. If your run moves the count across a band, the wording changes with it and that is
correct.

## Changing pure decision logic

A matcher, a schema leaf, a tier lookup, a normaliser — anything that is a function from
plain data to plain data — is where every drift in this repo has happened, nine of them,
each one silent. Add the case to `contract/conformance.json` in the same change. Both
runtimes answer that file, so a fix that lands in one build and not the other fails CI
instead of shipping under a green parity line.

`tests/test_parity.py` is the other half and does a different job: it proves a marker
string exists in each build. That catches a feature nobody ported; it cannot catch one
ported wrongly, and it once passed a row whose JS marker was a *comment describing the
mechanism*. Markers for prompts and prose, conformance for answers.

If the two builds must genuinely differ because the platform differs — URL parsing is the
real instance — use `out_by_runtime` and say in `why` what makes the difference correct.
It pins both answers, so either one moving still fails. It is not a way to excuse drift.

## Adding a search backend

`deepresearch/search.py`, standard library only. Add an implementation, register it in
`_IMPL`, and put it in `DEFAULT_CHAIN` where it belongs — general web first, then
independent indexes, then scholarly and practitioner sources.

Two requirements:

1. **Raise on a challenge page.** Several engines answer a rate-limited client with HTTP
   200 or 202 and a body that parses to zero results. Returning `[]` for that is a lie: it
   is indistinguishable from "the web contains nothing on this topic". Detect it and raise,
   so `_note` records a failure and `health()` reports it.
2. **Prefer fetchable URLs.** A link that redirects into a JavaScript challenge is worth
   nothing downstream. OpenAlex's `landing_page_url` is usually just the DOI again; its
   `pdf_url` is often a real publisher page. Reach for the one that can actually be read.

## Adding a fetch adapter

Reading a page is a fixed order of adapters, not a registry: `_FETCH_CHAIN` in
`deepresearch/search.py`. Unlike search backends, nothing selects a fetcher by name —
the order is the semantics — so the chain is a tuple and stays one. An adapter is a
module-level `attempt(url, cap, prev=None)` returning one of two shapes, never mixed:

1. **Serve — `(text, meta)`.** `text` is the page text, or `""` for a *named* refusal
   such as the unreadable-PDF one. A refusal is read provenance and serves; it must not
   fall through, or unreadable PDFs would come back as abstracts. A serve ends the walk.
2. **Fall through — `(None, why)`.** `why` is a plain string naming the failure, or
   `None` when this adapter was not applicable or has nothing to name. `""` is never a
   fall-through: an empty page is a serve.

`prev` carries the pair (adapter, why) of the last *named* fall-through, so a later
adapter can label its own meta with an earlier failure — `firecrawlFailed` is folded
only when the direct http read succeeds, `blockedBy` and `liveFetchFailed` travel the
same way, and nothing is shared mutable state.

Two ordering invariants are load-bearing. Both are enforced by the code and pinned by
effect tests, so a reorder fails loudly instead of drifting:

- `_via_firecrawl` stays the **immediate predecessor** of `_via_direct`, or the
  `firecrawlFailed` disclosure silently disappears — a visible no-op, never a mislabel.
- The walk's tail reads `prev[1]` unguarded, true only while `_via_direct`'s
  fall-through reason is never empty and nothing after it falls through with a reason.

Every branch of every adapter has an effect test in `tests/test_pipeline.py` (the
fetch-seam section at the foot of the file). Add yours in the same change: stub the
seam your adapter calls (`crossref_record`, `_get_bytes`, `_try_wayback`, …), drive
`searchmod.fetch`, and assert the `via` string and the meta keys. The prose gate is
not a chain-wide wrapper — it gates PDF text, scraper markdown and archive text, and
never direct HTML reads.

## Adding or changing a source tier, or a depth budget

Edit `contract/tiers.json` or `contract/depths.json` — **not** the Python and not the
JavaScript. Then run `python3 tools/sync_tiers.py` and commit what it regenerates. Both runtimes read
those files precisely so a domain cannot be graded T1 in one runtime and T3 in the other,
and so `quick` cannot mean 10 claims in one and 14 in the other. Both have happened. CI
checks that every rule compiles, every tier is rankable, and the generated JS blocks match
their source byte-for-byte.

Before promoting a host to T1, ask whether it is a *publisher* or a *resolver*. `doi.org`
resolves to anything, including a predatory journal; grading the resolver top-tier makes
that journal outrank an SEC filing. Resolvers belong in `resolvers`, and get `T?` until
something actually reads the record behind them.

## Changing a prompt

Prompts live inline, deliberately: they are the product, and a template indirection layer
makes them harder to read and review than the thing it saves. Keep them readable, and keep
the reason for a constraint next to the constraint.

If you widen a schema, split the call rather than adding a field. One call carrying four
responsibilities behind three levels of nesting failed 3 out of 3 live runs here, dropping
the same field every time. Raising `max_tokens` fixed truncation and did nothing for shape.

**Scope, added 2026-09-15 after a review cited this rule against `hypothesisNumber`.** The
rule is about RESPONSIBILITIES, not fields: what failed those three runs was one call
asked to do four unrelated jobs, and splitting it fixed the shape. A scalar added to an
item the call already returns — `hypothesisNumber` on an existing `hypothesisVerdicts`
entry — adds no responsibility, and splitting the synthesis call to fetch one integer
would cost a call and a round trip to obey the letter of a rule written about something
else. Adding a field is still the thing to justify in the diff; it is a judgement call
against this rationale, not an automatic no. The review was right that the rule as
written forbade it and that nothing cited an exemption.

## Things that will be rejected

- A benchmark number with no denominator, no date, and no committed log.
- Softening an honest failure message. If a run was rate-limited, the report says it was
  rate-limited — never "no sources were found".
- Removing a lens to make a tier cheaper. Two of N must refute, so with two lenses a 1–1
  split survives and the panel can never kill anything. Cut the claim count instead.
